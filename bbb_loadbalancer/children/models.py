import re
from hashlib import sha1
from urllib.parse import urlencode
from urllib.request import urlopen

from django.db import models
from django.utils.functional import cached_property
from bigbluebutton_api_python import BigBlueButton
from jxmlease import parse


class BBBServer(models.Model):
    url = models.CharField(max_length=255, default="")
    secret = models.CharField(max_length=255, default="")

    @cached_property
    def api(self):
        return BigBlueButton(self.url, self.secret)

    @cached_property
    def api_url(self):
        """
        Ensure the url used for api calls looks correct.
        """
        url = self.url
        if not re.match('/[http|https]:\/\/[a-zA-Z1-9.]*\/bigbluebutton\/api\//', url):
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

        # Basically urlencode but map True and False to lower case
        param_strings = []
        for key, value in params.items():
            if isinstance(value, bool):
                value = "true" if value else "false"
            else:
                value = str(value)
            param_strings.append(key + "=" + value)
        param_string = "&".join(param_strings)

        # Generate checksum
        secret_str = api_call + param_string + self.secret
        checksum = sha1(secret_str.encode('utf-8')).hexdigest()

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


class Meeting(models.Model):
    meeting_id = models.CharField(max_length=255, default="")
    internal_id = models.CharField(max_length=255, default="")
    server = models.ForeignKey(BBBServer, on_delete=models.CASCADE)

    def __str__(self):
        return self.meeting_id
