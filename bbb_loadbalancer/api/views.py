import hashlib
import logging
import re
import os.path
from collections import defaultdict
from functools import wraps

import httpx
from django.db.models import Count
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.views import View
from jxmlease import emit_xml, XMLDictNode
from rc_protocol import get_checksum

from bbb_loadbalancer import settings
from common_files.models import Meeting, BBBServer

_checksum_regex = re.compile(r"&?checksum=[^&]+")
_checksum_algos = [
    lambda string: hashlib.sha1(string.encode("utf-8")).hexdigest(),
    lambda string: hashlib.sha256(string.encode("utf-8")).hexdigest(),
]

logger = logging.getLogger(__name__)


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

        # Try different hashing algorithms
        for hash_algo in _checksum_algos:
            if hash_algo(endpoint + query_string + settings.SHARED_SECRET) == checksum:
                break
        # No checksum matched
        else:
            return XmlResponse(self.respond(False, "checksumError", "You did not pass the checksum security check"))

        # Get parameters as simple dict without checksum
        parameters = dict((key, request.GET.get(key)) for key in request.GET if key != "checksum")
        missing_parameters = [param for param in self.required_parameters if param not in parameters]
        if len(missing_parameters) > 0:
            return self.respond(False, "", "")  # TODO: error message

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

        if message:
            response["message"] = message
        if message_key:
            response["messageKey"] = message_key

        if data:
            response.update(data)

        return {"response": response}

    def process(self, parameters: dict):
        raise NotImplementedError


class Create(_GetView):
    required_parameters = ["meetingID"]

    def process(self, parameters: dict):
        meeting_id = parameters["meetingID"]

        # Primitive loadbalancing code
        server = BBBServer.objects.annotate(meetings=Count("meeting")).earliest("meetings")  # TODO pick at random

        # Create meeting
        response = server.send_api_request("create", parameters)
        if response["returncode"] == "SUCCESS" and not Meeting.running.filter(meeting_id=meeting_id).exists():
            Meeting.objects.create(
                meeting_id=response["meetingID"],
                internal_id=response["internalMeetingID"],
                server=server
            )
        return self.respond(data=response)


class Join(_GetView):
    required_parameters = ["fullName", "meetingID", "password"]

    def process(self, parameters: dict):
        meeting_id = parameters["meetingID"]

        try:
            meeting = Meeting.running.get(meeting_id=meeting_id)
        except Meeting.DoesNotExist:
            return self.respond(
                False, "notFound",
                "We could not find a meeting with that meeting ID - perhaps the meeting is not yet running?"
            )

        return HttpResponseRedirect(
            meeting.server.build_api_url("join", parameters)
        )


class IsMeetingRunning(_GetView):
    required_parameters = ["meetingID"]

    def process(self, parameters: dict):
        meeting_id = parameters["meetingID"]

        if Meeting.running.filter(meeting_id=meeting_id).exists():
            return self.respond(data={"running": "true"})
        else:
            return self.respond(data={"running": "false"})


class End(_GetView):
    required_parameters = ["password", "meetingID"]

    def process(self, parameters: dict):
        meeting_id = parameters["meetingID"]

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
    required_parameters = ["meetingID"]

    def process(self, parameters: dict):
        meeting_id = parameters["meetingID"]

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
    required_parameters = []

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
    required_parameters = []

    def process(self, parameters: dict):
        recordings = []
        if "recordID" in parameters:
            recordings = list(map(str.strip, parameters["recordID"].split(",")))
        elif "meetingID" in parameters:
            for meeting_id in map(str.strip, parameters["meetingID"].split(",")):
                for meeting in Meeting.objects.filter(meeting_id=meeting_id):
                    recordings.append(meeting.internal_id)

        url = os.path.join(settings.config.player.api_url, "getRecordings")
        params = {
            "recordings": recordings
        }
        params["checksum"] = get_checksum(params, settings.config.player.rcp_secret, "getRecordings")

        response = httpx.post(url, json=params, headers={"user-agent": "bbb-loadbalancer"})
        return self.respond(False, "notImplemented", "this endpoint is not quite implemented yet!")


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
    pass


class GetDefaultConfigXML(_GetView):
    pass


class GetRecordingTextTracks(_GetView):
    pass


class PutRecordingTestTracks(_GetView):
    pass
