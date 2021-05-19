from django.utils.functional import cached_property
from bigbluebutton_api_python import BigBlueButton

from common_files.models import *


class BBBServerDjango(BBBServer):
    def __init__(self):
        super().__init__()

    @cached_property
    def api(self):
        return BigBlueButton(self.url, self.secret)

    def get_absolute_url(self):
        return f"https://mconf.github.io/api-mate/#server={self.url}&sharedSecret={self.secret}"

    def __str__(self):
        return self.url


class MeetingDjango(Meeting):
    def __init__(self):
        super().__init__()

    def __str__(self):
        return self.meeting_id
