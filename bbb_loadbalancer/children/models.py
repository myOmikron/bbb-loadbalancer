from django.db import models
from django.utils.functional import cached_property
from bigbluebutton_api_python import BigBlueButton


class BBBServer(models.Model):
    url = models.CharField(max_length=255, default="")
    secret = models.CharField(max_length=255, default="")

    @cached_property
    def api(self):
        return BigBlueButton(self.url, self.secret)

    def get_absolute_url(self):
        return f"https://mconf.github.io/api-mate/#server={self.url}&sharedSecret={self.secret}"

    def __str__(self):
        return self.url


class Meeting(models.Model):
    meeting_id = models.CharField(max_length=255, default="")
    internal_id = models.CharField(max_length=255, default="")
    server = models.ForeignKey(BBBServer, on_delete=models.CASCADE)

    def __str__(self):
        return self.meeting_id
