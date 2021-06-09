import hashlib
import re
from urllib.parse import urlencode
from urllib.request import urlopen

from django.db import models
from django.db.models import Manager
from jxmlease import parse


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

    def build_api_url(self, api_call, params=None):
        if params is None:
            params = {}

        # BBB wants boolean as lower case but urlencode would produce first letter uppercase
        for key, value in params.items():
            if isinstance(value, bool):
                params[key] = str(value).lower()

        # Build query string
        param_string = urlencode(params)

        # Generate checksum
        secret_str = api_call + param_string + self.secret
        checksum = hashlib.sha1(secret_str.encode('utf-8')).hexdigest()

        # Build url
        return self.api_url + api_call + "?" + param_string + "&checksum=" + checksum

    def send_api_request(self, api_call, params=None, data=None):
        url = self.build_api_url(api_call, params)

        # GET request
        if data is None:
            response = urlopen(url).read()
        # POST request
        else:
            response = urlopen(url, data=urlencode(data).encode()).read()

        try:
            return parse(response)["response"]
        except Exception as e:
            raise RuntimeError("XMLSyntaxError", e.message)


class RunningMeetingsManager(Manager):

    def get_queryset(self):
        return super().get_queryset().filter(ended=False)


class Meeting(models.Model):
    objects = Manager()
    running = RunningMeetingsManager()

    meeting_id = models.CharField(max_length=255, default="")
    internal_id = models.CharField(max_length=255, default="")
    server = models.ForeignKey(BBBServer, on_delete=models.CASCADE)
    ended = models.BooleanField(default=False)
    load = models.IntegerField()
    create_query = models.JSONField(default=dict)

    def __str__(self):
        return self.meeting_id
