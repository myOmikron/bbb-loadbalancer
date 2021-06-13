import hashlib
import logging
from urllib.parse import urlencode
from urllib.request import urlopen

from jxmlease import parse

from api.response import EarlyResponse, respond

logger = logging.getLogger("bbb_api")


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
    url = build_api_url(self, api_call, params)

    # GET request
    if data is None:
        response = urlopen(url).read()
    # POST request
    else:
        try:
            response = urlopen(url, data=urlencode(data).encode()).read()
        except:
            logger.exception(f"Couldn't call a bbb's api: {self}")
            raise EarlyResponse(respond(
                False, "noResponse",
                "An internal server didn't respond. Try again in some seconds or contact your admin."
            )) from None

    try:
        return parse(response)["response"]
    except Exception as e:
        raise RuntimeError("XMLSyntaxError", e.message)
