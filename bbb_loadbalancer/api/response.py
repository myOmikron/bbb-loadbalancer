import logging
from functools import wraps
from xml.sax.xmlreader import AttributesImpl

from django.http import HttpResponse
from jxmlease import XMLCDATANode, emit_xml


logger = logging.getLogger("api")


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


class EarlyResponse(RuntimeError):

    def __init__(self, response: dict):
        super().__init__()
        self.response = response


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
