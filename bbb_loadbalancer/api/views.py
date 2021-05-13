import hashlib
import re
from functools import wraps

from django.http import HttpRequest, HttpResponse, QueryDict, HttpResponseRedirect
from django.views import View
from jxmlease import emit_xml

from bbb_loadbalancer import settings
from children.models import Meeting

_checksum_regex = re.compile(r"&checksum=[^&]+")
_checksum_algos = [
    lambda string: hashlib.sha1(string.encode("utf-8")).hexdigest(),
    lambda string: hashlib.sha256(string.encode("utf-8")).hexdigest(),
]


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
    pass


class Join(_GetView):
    required_parameters = ["fullName", "meetingID", "password"]

    def process(self, parameters: dict):
        full_name = parameters["fullName"]
        meeting_id = parameters["meetingID"]
        password = parameters["password"]

        try:
            meeting = Meeting.objects.get(meeting_id=meeting_id)
        except Meeting.DoesNotExist:
            return self.respond(
                False, "notFound",
                "We could not find a meeting with that meeting ID - perhaps the meeting is not yet running?"
            )

        return HttpResponseRedirect(
            meeting.server.api.get_join_meeting_url(
                full_name, meeting_id, password, dict(parameters)
            )
        )


class IsMeetingRunning(_GetView):
    required_parameters = ["meetingID"]

    def process(self, parameters: dict):
        meeting_id = parameters["meetingID"]

        if Meeting.objects.filter(meeting_id=meeting_id).exists():
            return self.respond(data={"running": "true"})
        else:
            return self.respond(data={"running": "false"})


class End(_GetView):
    pass


class GetMeetingInfo(_GetView):
    pass


class GetMeetings(_GetView):
    pass


class GetRecordings(_GetView):
    pass


class PublishRecordings(_GetView):
    pass


class DeleteRecordings(_GetView):
    pass


class UpdateRecordings(_GetView):
    pass


class GetDefaultConfigXML(_GetView):
    pass


class GetRecordingTextTracks(_GetView):
    pass


class PutRecordingTestTracks(_GetView):
    pass
