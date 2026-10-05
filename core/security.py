import hmac

from core import config

MAX_BODY = 256 * 1024


def api_key_ok(request):
    expected = config.get("INTEROP_API_KEY")
    supplied = request.headers.get("X-API-Key", "")
    return bool(expected) and hmac.compare_digest(expected.encode(), supplied.encode())
