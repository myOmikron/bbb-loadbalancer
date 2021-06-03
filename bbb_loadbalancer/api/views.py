import hashlib
import logging
import random
import re
import os.path
from collections import defaultdict
from functools import wraps
from xml.sax.xmlreader import AttributesImpl

import httpx
from django.db.models import Sum, Q
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.views import View
from jxmlease import emit_xml, XMLDictNode, XMLCDATANode
from rc_protocol import get_checksum

from bbb_loadbalancer import settings
from common_files.models import Meeting, BBBServer

_checksum_regex = re.compile(r"&?checksum=[^&]+")
_checksum_algos = [
    lambda string: hashlib.sha1(string.encode("utf-8")).hexdigest(),
    lambda string: hashlib.sha256(string.encode("utf-8")).hexdigest(),
]

logger = logging.getLogger(__name__)


class RawXMLString(XMLCDATANode):
    """
    Small hack to wrap xml string with jxmlease without parsing it first
    """

    def _emit_handler(self, content_handler, depth, pretty, newl, indent):
        if pretty:
            content_handler.ignorableWhitespace(depth * indent)
        content_handler.startElement(self.tag, AttributesImpl(self.xml_attrs))
        content = self.get_cdata()
        content_handler._finish_pending_start_element()               # Copied and modified from XMLGenerator.characters
        if not isinstance(content, str):                              #
            content_handler = str(content, content_handler._encoding) #
        content_handler._write(content)                               #
        content_handler.endElement(self.tag)
        if pretty and depth > 0:
            content_handler.ignorableWhitespace(newl)


@wraps(HttpResponse)
def XmlResponse(data, *args, **kwargs):
    return HttpResponse(emit_xml(data), *args, content_type="text/xml", **kwargs)


class _GetView(View):
    _response: dict
    required_parameters: list = []

    def get(self, request: HttpRequest, *args, **kwargs):
        # Get data for checksum test
        endpoint = request.path.split("/")[-1]
        checksum = request.GET.get("checksum")
        query_string = _checksum_regex.sub("", request.META["QUERY_STRING"])

        logger.info(f"GET {request.get_full_path()}")

        # Try different hashing algorithms
        for hash_algo in _checksum_algos:
            if hash_algo(endpoint + query_string + settings.SHARED_SECRET) == checksum:
                break
        # No checksum matched
        else:
            return XmlResponse(self.respond(False, "checksumError", "You did not pass the checksum security check"))

        # Get parameters as simple dict without checksum
        parameters = dict((key, request.GET.get(key)) for key in request.GET if key != "checksum")

        # Call to subclass for actual processing logic
        response = self.process(parameters)
        assert response is not None, \
            "The process method didn't return a response"

        # Wrap response with XmlResponse if necessary
        if isinstance(response, dict):
            return XmlResponse(response)
        else:
            return response

    @staticmethod
    def respond(success: bool = True,
                message_key: str = None,
                message: str = None,
                data: dict = None) -> dict:
        """
        Create a response dict

        :param success: whether the call was successful (when False, message_key and message are required)
        :type success: bool
        :param message_key: a camelcase word to describe what happened (required if success is False)
        :type message_key: str
        :param message: a short description of what happened (required if success is False)
        :type message: str
        :param data: a dictionary containing any endpoint specific response data
        :type data: dict
        :return: response dictionary
        :rtype: dict
        """
        response = {}

        if success:
            response["returncode"] = "SUCCESS"
        else:
            response["returncode"] = "FAILED"
            assert message_key is not None and message is not None, \
                "Arguments 'message' and 'message_key' are required when 'success' is False"
            logger.info(f"FAILED: {message_key} | {message}")

        if message:
            response["message"] = message
        if message_key:
            response["messageKey"] = message_key

        if data:
            response.update(data)

        return {"response": response}

    def missing_meeting_id(self) -> dict:
        return self.respond(
            False, "missingParamMeetingID", "You must specify a meeting ID for the meeting."
        )

    def process(self, parameters: dict):
        raise NotImplementedError


class DefaultView(_GetView):

    def get(self, request: HttpRequest, *args, **kwargs):
        logger.info(f"GET {request.path}")
        return XmlResponse(self.respond(False, "unsupportedRequest", "This request is not supported."))


class Create(_GetView):

    @staticmethod
    def get_next_server(queryset=None) -> BBBServer:
        """
        Get the next server to create a meeting on.

        Get a list of the servers with the smallest load total and return one at random
        :param queryset: optional queryset to limit the search
        :return: a server with the smallest load total
        """
        if queryset is None:
            queryset = BBBServer.objects

        # Get all servers with a calculated load attribute
        servers = queryset \
            .annotate(load=Sum("meeting__load", filter=Q(meeting__ended=False))) \
            .order_by("load") \
            .all()

        # Remove server above smallest load
        smallest_load = servers[0].load
        for i in range(len(servers)):
            server = servers[i]
            if server.load != smallest_load:
                break
        else:
            i = len(servers)
        servers = servers[:i]

        # Choose one at random
        return random.choice(servers)

    def process(self, parameters: dict):
        # Require meetingID
        try:
            meeting_id = parameters["meetingID"]
        except KeyError:
            return self.missing_meeting_id()

        server = self.get_next_server()

        # Create meeting
        response = server.send_api_request("create", parameters)
        if response["returncode"] == "SUCCESS" and not Meeting.running.filter(meeting_id=meeting_id).exists():
            Meeting.objects.create(
                meeting_id=response["meetingID"],
                internal_id=response["internalMeetingID"],
                server=server,
                load=parameters["load"] if "load" in parameters else 1,
            )
            logger.info(f"SUCCESS: created on f{server}")
        return self.respond(data=response)


class Join(_GetView):

    def process(self, parameters: dict):
        # Require meetingID
        try:
            meeting_id = parameters["meetingID"]
        except KeyError:
            return self.missing_meeting_id()

        try:
            meeting = Meeting.running.get(meeting_id=meeting_id)
        except Meeting.DoesNotExist:
            return self.respond(
                False, "notFound",
                "We could not find a meeting with that meeting ID - perhaps the meeting is not yet running?"
            )

        redirect = meeting.server.build_api_url("join", parameters)
        logger.info(f"-> {redirect}")
        return HttpResponseRedirect(redirect)


class IsMeetingRunning(_GetView):

    def process(self, parameters: dict):
        # Require meetingID
        try:
            meeting_id = parameters["meetingID"]
        except KeyError:
            return self.missing_meeting_id()

        if Meeting.running.filter(meeting_id=meeting_id).exists():
            return self.respond(data={"running": "true"})
        else:
            return self.respond(data={"running": "false"})


class End(_GetView):

    def process(self, parameters: dict):
        # Require meetingID
        try:
            meeting_id = parameters["meetingID"]
        except KeyError:
            return self.missing_meeting_id()

        try:
            meeting = Meeting.running.get(meeting_id=meeting_id)
        except Meeting.DoesNotExist:
            return self.respond(
                False, "notFound",
                "We could not find a meeting with that meeting ID - perhaps the meeting is not yet running?"
            )

        response = meeting.server.send_api_request("end", parameters)
        if response["returncode"] == "SUCCESS":
            meeting.ended = True
            meeting.save()

        return self.respond(data=response)


class GetMeetingInfo(_GetView):

    def process(self, parameters: dict):
        # Require meetingID
        try:
            meeting_id = parameters["meetingID"]
        except KeyError:
            return self.missing_meeting_id()

        try:
            meeting = Meeting.running.get(meeting_id=meeting_id)
        except Meeting.DoesNotExist:
            return self.respond(
                False, "notFound",
                "We could not find a meeting with that meeting ID - perhaps the meeting is not yet running?"
            )

        response = meeting.server.send_api_request("getMeetingInfo", parameters)
        return XmlResponse({"response": response})


class GetMeetings(_GetView):

    def process(self, parameters: dict):
        meetings = []
        for server in BBBServer.objects.all():
            response = server.send_api_request("getMeetings")

            if "messageKey" in response and response["messageKey"] == "noMeetings":
                continue

            meetings_data = response["meetings"]["meeting"]
            # There is only one meeting
            if isinstance(meetings_data, XMLDictNode):
                meetings.append(meetings_data)
            else:
                for meeting in meetings_data:
                    meetings.append(meeting)

        if len(meetings) == 0:
            return self.respond(
                True, "noMeetings",
                "no meetings were found on this server"
            )
        else:
            return self.respond(True, data={"meetings": {"meeting": meetings}})


class GetRecordings(_GetView):

    def process(self, parameters: dict):
        recordings = []
        if "recordID" in parameters:
            recordings = list(map(str.strip, parameters["recordID"].split(",")))
        elif "meetingID" in parameters:
            for meeting_id in map(str.strip, parameters["meetingID"].split(",")):
                for meeting in Meeting.objects.filter(meeting_id=meeting_id):
                    recordings.append(meeting.internal_id)

        # Forward request to player
        url = os.path.join(settings.config.player.api_url, "getRecordings")
        params = {
            "recordings": recordings
        }
        params["checksum"] = get_checksum(params, settings.config.player.rcp_secret, "getRecordings")
        #response = httpx.post(url, json=params, headers={"user-agent": "bbb-loadbalancer"})
        response = httpx.get("http://127.0.0.1:8000/bigbluebutton/api/getMeetings?checksum=foo")

        # Strip the leading <?xml version="1.0" encoding="utf-8"?>
        xml_response = response.text
        xml_response = xml_response[xml_response.find("\n"):]

        # Wrap player's response
        if xml_response:  # TODO check if no recordings
            return self.respond(
                True, "noRecordings", "There are no recordings for the meeting(s).",
                data={"recordings": {}}
            )
        else:
            return self.respond(
                True,
                data={"recordings": RawXMLString(xml_response)}
            )


class PublishRecordings(_GetView):
    required_parameters = ["recordID", "publish"]

    def process(self, parameters: dict):
        # Get a list of meetings to be published for each server
        meetings_per_server = defaultdict(list)
        for internal_id in map(str.strip, parameters["recordID"].split(",")):
            try:
                meeting = Meeting.objects.get(internal_id=internal_id)
                meetings_per_server[meeting.server].append(internal_id)
            except Meeting.DoesNotExist:
                pass

        # Call publish on every server once with all its meetings
        responses = []
        for server, meetings in meetings_per_server.items():
            responses.append(
                server.send_api_request("publishRecordings", {
                    "recordID": ",".join(meetings),
                    "publish": parameters["publish"]
                })
            )

        # If any recording was published successfully just call everything a success (bbb behaviour)
        for response in responses:
            if response["returncode"] == "SUCCESS":
                break
        else:
            return self.respond(
                   False, "notFound",
                   "We could not find recordings"
               )
        return self.respond(True, data={"published": parameters["publish"]})


class DeleteRecordings(_GetView):
    required_parameters = ["recordID"]

    def process(self, parameters: dict):
        url = os.path.join(settings.config.player.api_url, "deleteRecordings")
        params = {
            "recordings": [record_id.strip() for record_id in parameters["recordID"].split(",")]
        }
        params["checksum"] = get_checksum(params, settings.config.player.rcp_secret, "deleteRecordings")

        response = httpx.post(url, json=params, headers={"user-agent": "bbb-loadbalancer"}).json()
        if response["success"]:
            return self.respond(True)
        else:
            return self.respond(False, "emptyList", response["message"])


class UpdateRecordings(_GetView):
    required_parameters = ["recordID"]

    def process(self, parameters: dict):
        # Get a parameters dict without the 'recordID'
        meta_parameters = dict((key, value) for key, value in parameters.items() if key != "recordID")

        # Get a list of meetings to be updated for each server
        meetings_per_server = defaultdict(list)
        for internal_id in map(str.strip, parameters["recordID"].split(",")):
            try:
                meeting = Meeting.objects.get(internal_id=internal_id)
                meetings_per_server[meeting.server].append(internal_id)
            except Meeting.DoesNotExist:
                pass

        # Call update on every server once with all its meetings
        responses = []
        for server, meetings in meetings_per_server.items():
            responses.append(
                server.send_api_request("updateRecordings", {
                    "recordID": ",".join(meetings),
                    **meta_parameters,
                })
            )

        # If any recording was updated successfully just call everything a success (bbb behaviour)
        for response in responses:
            if response["returncode"] == "SUCCESS":
                break
        else:
            return self.respond(
                False, "notFound",
                "We could not find recordings"
            )
        return self.respond(True, data={"updated": "true"})


class GetDefaultConfigXML(_GetView):
    pass


class GetRecordingTextTracks(_GetView):
    pass


class PutRecordingTestTracks(_GetView):
    pass

# Custom API endpoints

class Move(_GetView):

    def process(self, parameters: dict):
        # Require meetingID
        try:
            meeting_id = parameters["meetingID"]
        except KeyError:
            return self.missing_meeting_id()

        try:
            meeting = Meeting.objects.get(meeting_id=meeting_id)
        except Meeting.DoesNotExist:
            return self.respond(
                False, "notFound",
                "We could not find a meeting with that meeting ID - perhaps the meeting is not yet running?"
            )

        if "serverID" in parameters:
            try:
                server = BBBServer.objects.get(id=parameters["serverID"])
            except BBBServer.DoesNotExist:
                return self.respond(
                    False, "notFound",
                    "We don't have a server with that server ID"
                )
        else:
            server = Create.get_next_server(BBBServer.objects.exclude(id=meeting.server.id))

        if server == meeting.server:
            return self.respond(False, "sameServer", "Origin and destination server are the same.")

        # End meeting
        response = meeting.server.send_api_request("end", {"meetingID": meeting_id, "password": ""})
        if response["returncode"] == "SUCCESS":
            meeting.ended = True
            meeting.save()
        else:
            return self.respond(data=response)

        # Create meeting
        response = server.send_api_request("create", {})  # TODO save original params
        if response["returncode"] == "SUCCESS" and not Meeting.running.filter(meeting_id=meeting_id).exists():
            Meeting.objects.create(
                meeting_id=response["meetingID"],
                internal_id=response["internalMeetingID"],
                server=server,
                load=parameters["load"] if "load" in parameters else 1,
            )
        return self.respond(data=response)
