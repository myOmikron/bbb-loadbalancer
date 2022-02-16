import json

from django.conf import settings
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from rc_protocol import validate_checksum

from common_files.models import BBBServer


@method_decorator(csrf_exempt, name='dispatch')
class RcpApi(View):
    endpoint: str = ""
    secret_name: str = "MONITORING_SECRET"
    time_delta_name: str = "MONITORING_TIME_DELTA"

    def _check_auth(self, request, params: dict, then: str):
        checksum: str = request.headers.get("Authorization", None)
        if checksum is None:
            return JsonResponse({"success": False, "info": "Authentication failed"}, status=401)

        if not validate_checksum(
                request=params,
                checksum=checksum.strip(),
                shared_secret=getattr(settings, self.secret_name),
                salt=self.endpoint,
                time_delta=getattr(settings, self.time_delta_name)):
            return JsonResponse({"success": False, "info": "Authorization failed"}, status=403)

        try:
            return getattr(self, then)(request, params)
        except NotImplementedError:
            return JsonResponse({"success": False, "info": "Method not allowed"}, status=405)

    def get(self, request, *args, **kwargs):
        return self._check_auth(request, request.GET.dict(), then="inner_get")

    def post(self, request, *args, **kwargs):
        try:
            params = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"success": False, "info": "JSON could not be decoded"}, status=400)

        return self._check_auth(request, params, then="inner_post")

    def inner_get(self, request, params):
        raise NotImplementedError

    def inner_post(self, request, params):
        raise NotImplementedError


class GetServers(RcpApi):

    def inner_get(self, request, params):
        return JsonResponse({"success": True, "info": "Ok", "servers": {
            "disabled": BBBServer.objects.filter(state=BBBServer.DISABLED).count(),
            "enabled": BBBServer.objects.filter(state=BBBServer.ENABLED).count(),
            "panic": BBBServer.objects.filter(state=BBBServer.PANIC).count(),
            "total": BBBServer.objects.count(),
        }})

    def inner_post(self, request, params):
        raise NotImplementedError
