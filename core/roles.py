"""Role-based access control. Roles are Django Groups; permissions are strings defined here."""
from functools import wraps

from django.contrib.auth.models import Group
from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseForbidden

ALL_PERMS = [
    "catalog.view", "catalog.edit", "tag.manage", "circ.process", "inventory.run",
    "reports.view", "members.view", "members.edit", "gate.view", "gate.simulate",
    "admin.system",
]

ROLE_PERMS = {
    "Admin": {"*"},
    "Librarian": {
        "catalog.view", "catalog.edit", "tag.manage", "circ.process", "inventory.run",
        "reports.view", "members.view", "members.edit", "gate.view", "gate.simulate",
    },
    "Circulation": {"catalog.view", "circ.process", "members.view"},
    "Viewer": {"catalog.view", "reports.view"},
}


def ensure_roles():
    for name in ROLE_PERMS:
        Group.objects.get_or_create(name=name)


def user_perms(user):
    if not user.is_authenticated:
        return set()
    if user.is_superuser:
        return {"*"}
    perms = set()
    for name in user.groups.values_list("name", flat=True):
        perms |= ROLE_PERMS.get(name, set())
    return perms


def has_perm(user, perm):
    perms = user_perms(user)
    return "*" in perms or perm in perms


def require_perm(perm):
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not has_perm(request.user, perm):
                from core import audit

                audit.log(request.user, "ACCESS_DENIED", perm, request.path)
                return HttpResponseForbidden("Your role does not allow this action.")
            return view(request, *args, **kwargs)

        return wrapped

    return decorator
