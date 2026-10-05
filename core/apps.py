from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "core"

    def ready(self):
        from django.contrib.auth.signals import user_logged_in, user_login_failed

        from core import audit

        def _ok(sender, request, user, **kw):
            audit.log(user, "LOGIN", "", "login ok")

        def _fail(sender, credentials, request=None, **kw):
            audit.log(credentials.get("username", "?"), "LOGIN_FAILED", "", "bad credentials")

        user_logged_in.connect(_ok, dispatch_uid="audit_login_ok")
        user_login_failed.connect(_fail, dispatch_uid="audit_login_fail")
