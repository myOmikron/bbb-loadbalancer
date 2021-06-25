import re

from django.db import models
from django.db.models import Manager


class BBBServer(models.Model):
    ENABLED = "ENABLED"
    DISABLED = "DISABLED"
    PANIC = "PANIC"

    server_id = models.IntegerField(unique=True)
    url = models.CharField(max_length=255, default="")
    secret = models.CharField(max_length=255, default="")
    state = models.CharField(max_length=255, default=ENABLED,
                             choices=((ENABLED, "enabled"), (DISABLED, "disabled"), (PANIC, "panic")))
    reachable = models.BooleanField(default=True)

    @property
    def api_url(self):
        """
        Ensure the url used for api calls looks correct.
        """
        url = self.url
        if not re.match(r'/(http|https)://[a-zA-Z1-9.]*/bigbluebutton/api//', url):
            if not url.startswith("http://") and not url.startswith("https://"):
                url = "https://" + url
            if not url.endswith("/bigbluebutton/api/"):
                url = url[:(url.find("/", 8) if url.find("/", 8) != -1 else len(url))] + "/bigbluebutton/api/"
        return url

    def get_absolute_url(self):
        """
        Provide a link to api mate in django's admin site
        """
        return f"https://mconf.github.io/api-mate/#server={self.url}&sharedSecret={self.secret}"

    def __str__(self):
        return self.url


class RunningMeetingsManager(Manager):

    def get_queryset(self):
        return super().get_queryset().filter(ended=False)


class Meeting(models.Model):
    TEMP_INTERNAL_ID = "**TEMP**"

    objects = Manager()
    running = RunningMeetingsManager()

    meeting_id = models.CharField(max_length=255, default="")
    internal_id = models.CharField(max_length=255, default="")
    server = models.ForeignKey(BBBServer, on_delete=models.CASCADE)
    ended = models.BooleanField(default=False)
    load = models.IntegerField()
    create_query = models.JSONField(default=dict)
    created = models.DateTimeField(auto_now_add=True)
    moved_to = models.ForeignKey("Meeting", on_delete=models.CASCADE, null=True, blank=True, default=None)

    def __str__(self):
        return self.meeting_id
