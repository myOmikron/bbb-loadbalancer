import hashlib
import json
import logging
import re
import os.path
from collections import defaultdict
from datetime import datetime, timedelta

import httpx
from django.http import HttpRequest, HttpResponseRedirect
from django.views import View
from jxmlease import XMLDictNode
from rc_protocol import get_checksum, validate_checksum

from api.bbb_api import send_api_request, build_api_url
from api.logic import get_next_server, create_meeting, config, Loadbalancer
from api.response import XmlResponse, EarlyResponse, RawXMLString, respond
from bbb_loadbalancer import settings
from common_files.models import Meeting, BBBServer

_checksum_regex = re.compile(r"&?checksum=([^&]+)")
_checksum_algos = [
    lambda string: hashlib.sha1(string.encode("utf-8")).hexdigest(),
    lambda string: hashlib.sha256(string.encode("utf-8")).hexdigest(),
]

logger = logging.getLogger("api")


class _GetView(View):
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
            return XmlResponse(respond(False, "checksumError", "You did not pass the checksum security check"))

        # Get parameters as simple dict without checksum
        parameters = dict((key, request.GET.get(key)) for key in request.GET if key != "checksum")

        # Call to subclass for actual processing logic
        try:
            response = self.process(parameters, request)
            assert response is not None, \
                "The process method didn't return a response"
        except EarlyResponse as early_response:
            response = early_response.response
        except BaseException:
            logger.exception("FAILED due to exception:")
            response = respond(False, "internalError", "An internal server error occurred.")

        # Wrap response with XmlResponse if necessary
        if isinstance(response, dict):
            return XmlResponse(response)
        else:
            return response

    def get_meeting_id(self, parameters: dict) -> str:
        """
        Helper method to get the meetingID and respond with an error if it's missing
        :param parameters: The parameters from the process method call
        :type parameters: dict
        :return: meetingID
        :rtype: str
        :raises EarlyResponse: missingParamMeetingID
        """
        if "meetingID" in parameters:
            return parameters["meetingID"]
        else:
            raise EarlyResponse(respond(
                False, "missingParamMeetingID",
                "You must specify a meeting ID for the meeting."
            ))

    def get_meeting(self, parameters: dict) -> Meeting:
        """
        Helper method to get the running meeting and respond with an error if there is none
        :param parameters: The parameters from the process method call
        :type parameters: dict
        :return: running meeting
        :rtype: Meeting
        :raises EarlyResponse: notFound
        """
        meeting_id = self.get_meeting_id(parameters)
        try:
            return Meeting.running.get(meeting_id=meeting_id)
        except Meeting.DoesNotExist:
            raise EarlyResponse(respond(
                False, "notFound",
                "We could not find a meeting with that meeting ID - perhaps the meeting is not yet running?"
            )) from None

    def process(self, parameters: dict, request: HttpRequest):
        raise NotImplementedError


class DefaultView(View):

    def get(self, request: HttpRequest, *args, **kwargs):
        logger.info(f"GET {request.path}")
        return XmlResponse(respond(False, "unsupportedRequest", "This request is not supported."))


# --------------------------- #
# Bigbluebutton API endpoints #
# --------------------------- #

class Index(View):

    def get(self, request: HttpRequest, *args, **kwargs):
        return XmlResponse(respond(True, data={"version": "2.0"}))


class Create(_GetView):

    def process(self, parameters: dict, request: HttpRequest):
        meeting, response = create_meeting(
            get_next_server(),
            self.get_meeting_id(parameters),
            parameters,
        )

        if response["returncode"] == "SUCCESS":
            logger.info(f"SUCCESS: created on {meeting.server}")

        return respond(data=response)


class Join(_GetView):

    def process(self, parameters: dict, request: HttpRequest):
        meeting = self.get_meeting(parameters)
        redirect = build_api_url(meeting.server, "join", parameters)
        logger.info(f"-> {redirect}")
        response = HttpResponseRedirect(redirect)

        # Store query string in cookie
        parameters["checksum"] = get_checksum(parameters, Loadbalancer.secret, use_time_component=False, salt="rejoin")
        response.set_cookie(
            "bbb_join",
            json.dumps(parameters),
            expires=datetime.now() + timedelta(days=7),
            domain=config.hostname,
            secure=True,
            httponly=True,
            samesite='Strict',
        )
        return response


class IsMeetingRunning(_GetView):

    def process(self, parameters: dict, request: HttpRequest):
        meeting_id = self.get_meeting_id(parameters)

        if Meeting.running.filter(meeting_id=meeting_id).exists():
            return respond(data={"running": "true"})
        else:
            return respond(data={"running": "false"})


class End(_GetView):

    def process(self, parameters: dict, request: HttpRequest):
        meeting = self.get_meeting(parameters)

        response = send_api_request(meeting.server, "end", parameters)
        if response["returncode"] == "SUCCESS":
            meeting.ended = True
            meeting.save()

        return respond(data=response)


class GetMeetingInfo(_GetView):

    def process(self, parameters: dict, request: HttpRequest):
        meeting = self.get_meeting(parameters)
        response = send_api_request(meeting.server, "getMeetingInfo", parameters)
        return XmlResponse({"response": response})


class GetMeetings(_GetView):

    @staticmethod
    def from_server(server: BBBServer) -> list:
        """
        Get all meetings on a server

        :param server: server to get meetings from
        :return: list of meetings (meetings are dicts)
        """
        if not server.enabled:
            return []

        response = send_api_request(server, "getMeetings")

        if "messageKey" in response and response["messageKey"] == "noMeetings":
            return []  # No meetings

        meetings_data = response["meetings"]["meeting"]
        if isinstance(meetings_data, XMLDictNode):
            return [meetings_data]  # One meeting

        else:
            return list(meetings_data)  # Multiple meetings

    def process(self, parameters: dict, request: HttpRequest):
        meetings = []
        for server in BBBServer.objects.all():
            meetings += self.from_server(server)

        if len(meetings) == 0:
            return respond(
                True, "noMeetings",
                "no meetings were found on this server"
            )
        else:
            return respond(True, data={"meetings": {"meeting": meetings}})


class GetRecordings(_GetView):

    def process(self, parameters: dict, request: HttpRequest):
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
        params["checksum"] = get_checksum(params, settings.config.player.rcp_secret, salt="getRecordings")
        response = httpx.post(url, json=params, headers={"user-agent": "bbb-loadbalancer"}).text

        # Wrap player's response
        if not response:
            return respond(
                True, "noRecordings", "There are no recordings for the meeting(s).",
                data={"recordings": {}}
            )
        else:
            return respond(
                True,
                data={"recordings": RawXMLString(response)}
            )


class PublishRecordings(_GetView):
    required_parameters = ["recordID", "publish"]

    def process(self, parameters: dict, request: HttpRequest):
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
            if not server.enabled:
                continue

            responses.append(
                send_api_request(server, "publishRecordings", {
                    "recordID": ",".join(meetings),
                    "publish": parameters["publish"]
                })
            )

        # If any recording was published successfully just call everything a success (bbb behaviour)
        for response in responses:
            if response["returncode"] == "SUCCESS":
                break
        else:
            return respond(
                   False, "notFound",
                   "We could not find recordings"
               )
        return respond(True, data={"published": parameters["publish"]})


class DeleteRecordings(_GetView):
    required_parameters = ["recordID"]

    def process(self, parameters: dict, request: HttpRequest):
        url = os.path.join(settings.config.player.api_url, "deleteRecordings")
        params = {
            "recordings": [record_id.strip() for record_id in parameters["recordID"].split(",")]
        }
        params["checksum"] = get_checksum(params, settings.config.player.rcp_secret, salt="deleteRecordings")

        response = httpx.post(url, json=params, headers={"user-agent": "bbb-loadbalancer"}).json()
        if response["success"]:
            return respond(True)
        else:
            return respond(False, "emptyList", response["message"])


class UpdateRecordings(_GetView):
    required_parameters = ["recordID"]

    def process(self, parameters: dict, request: HttpRequest):
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
            if not server.enabled:
                continue

            responses.append(
                send_api_request(server, "updateRecordings", {
                    "recordID": ",".join(meetings),
                    **meta_parameters,
                })
            )

        # If any recording was updated successfully just call everything a success (bbb behaviour)
        for response in responses:
            if response["returncode"] == "SUCCESS":
                break
        else:
            return respond(
                False, "notFound",
                "We could not find recordings"
            )
        return respond(True, data={"updated": "true"})


class GetDefaultConfigXML(_GetView):
    pass


class GetRecordingTextTracks(_GetView):
    pass


class PutRecordingTestTracks(_GetView):
    pass


# -------------------- #
# Custom API endpoints #
# -------------------- #

class Move(_GetView):

    def process(self, parameters: dict, request: HttpRequest):
        meeting = self.get_meeting(parameters)

        if "serverID" in parameters:
            try:
                server = BBBServer.objects.get(server_id=parameters["serverID"])
            except BBBServer.DoesNotExist:
                return respond(
                    False, "notFound",
                    "We don't have a server with that server ID"
                )
        else:
            server = get_next_server(BBBServer.objects.exclude(id=meeting.server.id))

        if server == meeting.server:
            return respond(False, "sameServer", "Origin and destination server are the same.")

        # End meeting
        response = send_api_request(meeting.server,
            "end", {"meetingID": meeting.meeting_id, "password": meeting.create_query["moderatorPW"]}
        )
        if response["returncode"] == "SUCCESS":
            meeting.ended = True
            meeting.save()
        else:
            return respond(data=response)

        # Create meeting
        new_meeting, response = create_meeting(server, meeting.meeting_id, meeting.create_query)
        if response["returncode"] == "SUCCESS":
            logger.info(f"SUCCESS: moved from {meeting.server} to {new_meeting.server}")
            meeting.moved_to = new_meeting
            meeting.save()

        return respond(data=response)


class GetStatistics(_GetView):

    meeting_attributes = ["meetingID", "participantCount", "listenerCount", "voiceParticipantCount", "videoCount"]

    def process(self, parameters: dict, request: HttpRequest):
        servers = []
        for server in BBBServer.objects.all():
            meetings = []
            for meeting in GetMeetings.from_server(server):
                meetings.append(dict(
                    (attr, meeting[attr]) for attr in self.meeting_attributes
                ))
            servers.append({"serverID": server.server_id, "meetings": {"meeting": meetings}})

        return respond(True, data={"servers": {"server": servers}})


class Rejoin(_GetView):

    def process(self, parameters: dict, request: HttpRequest):
        try:
            meeting = Meeting.objects.get(id=parameters["meetingID"])
        except KeyError:
            return respond(False, "missingParamMeetingID", "You must specify a meeting ID for the meeting.")
        except Meeting.DoesNotExist:
            return respond(
                False, "notFound",
                "We could not find a meeting with that meeting ID - perhaps the meeting is not yet running?"
            )

        if meeting.moved_to is None:
            if "logoutURL" in meeting.create_query:
                return HttpResponseRedirect(meeting.create_query["logoutURL"])
            else:
                return HttpResponseRedirect(config.logoutURL)
        else:
            # Follow moved_to links
            new_meeting = meeting.moved_to
            while new_meeting.moved_to is not None:
                new_meeting = new_meeting.moved_to

            # Get parameters from last join
            cookie = request.COOKIES.get("bbb_join")
            if cookie is None:
                return respond(
                    False, "noJoinCookie",
                    "Your meeting was moved, but we couldn't find your join cookie. Please join again."
                )
            parameters = json.loads(cookie)
            if validate_checksum(parameters, Loadbalancer.secret, salt="rejoin", use_time_component=False):
                return HttpResponseRedirect(build_api_url(new_meeting.server, "join", parameters))
            else:
                return respond(False, "checksumError", "You did not pass the checksum security check")
