from core.roles import ALL_PERMS, has_perm
from core.version import current_version


def nav(request):
    user = getattr(request, "user", None)
    can = {p.replace(".", "_"): bool(user and has_perm(user, p)) for p in ALL_PERMS}
    return {"can": can, "app_version": current_version()}
