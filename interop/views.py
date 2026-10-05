from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core.security import MAX_BODY, api_key_ok
from interop import ncip, sip2


def _guard(request):
    if not api_key_ok(request):
        return HttpResponse("invalid or missing X-API-Key", status=401, content_type="text/plain")
    if len(request.body) > MAX_BODY:
        return HttpResponse("body too large", status=413, content_type="text/plain")
    return None


@csrf_exempt
@require_POST
def ncip_endpoint(request):
    denied = _guard(request)
    return denied or HttpResponse(ncip.handle(request.body.decode("utf-8", "replace")), content_type="application/xml")


@csrf_exempt
@require_POST
def sip2_endpoint(request):
    denied = _guard(request)
    return denied or HttpResponse(sip2.handle(request.body.decode("utf-8", "replace")), content_type="text/plain")
