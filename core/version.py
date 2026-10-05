from django.conf import settings


def current_version():
    try:
        return (settings.BASE_DIR / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"
