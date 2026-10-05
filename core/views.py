import platform
import sys
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.db import connection
from django.db.models import Count, Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from core import audit, config
from core.models import AuditLog, Setting
from core.roles import require_perm
from core.version import current_version


def _health():
    from catalog.models import Item

    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
        db = "ok"
        items = Item.objects.count()
    except Exception as exc:  # health must never crash
        db, items = f"error: {exc.__class__.__name__}", None
    return {
        "status": "ok" if db == "ok" else "degraded",
        "version": current_version(),
        "database": db,
        "items": items,
        "rfid_mode": config.get("RFID_MODE"),
        "lms_online": config.get_bool("LMS_ONLINE"),
        "time": timezone.now().isoformat(),
    }


def health(request):
    return JsonResponse(_health())


@login_required
def dashboard(request):
    from catalog.models import Biblio, Item
    from circulation.models import Fine, Loan, Transaction
    from members.models import Member
    from notifications.models import Notification
    from rfid.models import GateEvent, RFIDTag

    now = timezone.now()
    days = []
    for offset in range(6, -1, -1):
        day = (now - timedelta(days=offset)).date()
        count = Transaction.objects.filter(ts__date=day, success=True).count()
        days.append({"label": day.strftime("%d %b"), "count": count})
    peak = max([d["count"] for d in days] + [1])
    for d in days:
        d["pct"] = int(d["count"] * 100 / peak)
    fines = Fine.objects.filter(paid=False).aggregate(total=Sum("amount"))["total"] or 0
    stats = {
        "titles": Biblio.objects.count(),
        "items": Item.objects.count(),
        "tagged": RFIDTag.objects.count(),
        "members": Member.objects.count(),
        "active_loans": Loan.objects.filter(returned_at__isnull=True).count(),
        "overdue": Loan.objects.filter(returned_at__isnull=True, due_at__lt=now).count(),
        "fines": fines,
        "gate_alerts": GateEvent.objects.filter(alarm=True, ts__gte=now - timedelta(days=7)).count(),
        "queued": Notification.objects.filter(status="QUEUED").count(),
        "denied_today": Transaction.objects.filter(ts__date=now.date(), success=False).count(),
    }
    top_ops = list(
        Transaction.objects.values("operator").annotate(n=Count("id")).order_by("-n")[:5]
    )
    return render(request, "dashboard.html", {"stats": stats, "days": days, "top_ops": top_ops})


def smartcard_login(request):
    from rfid.adapters import get_adapter

    if request.method == "POST":
        uid = request.POST.get("card_uid", "").strip()
        username = get_adapter("smartcard").authenticate(uid)
        if username:
            user = get_user_model().objects.filter(username=username, is_active=True).first()
            if user:
                login(request, user, backend="django.contrib.auth.backends.ModelBackend")
                audit.log(user, "SMARTCARD_LOGIN", uid, "smart-card login ok")
                return redirect("dashboard")
        audit.log(uid or "?", "SMARTCARD_LOGIN_FAILED", uid, "unknown or inactive card")
        messages.error(request, "Card not recognised. Use your password instead or contact an administrator.")
    return render(request, "smartcard.html")


@require_perm("admin.system")
def system(request):
    if request.method == "POST":
        key = request.POST.get("key", "")
        if key in config.DEFAULTS and key not in ("INTEROP_API_KEY", "UPDATE_SIGNING_KEY"):
            Setting.objects.update_or_create(key=key, defaults={"value": request.POST.get("value", "")[:255]})
            audit.log(request.user, "SETTING_CHANGED", key, request.POST.get("value", ""))
            messages.success(request, f"Saved setting {key}.")
        return redirect("system")
    settings_view = {k: config.get(k) for k in config.DEFAULTS if k not in ("INTEROP_API_KEY", "UPDATE_SIGNING_KEY")}
    return render(
        request,
        "system.html",
        {
            "health": _health(),
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "settings_view": settings_view,
            "audit": AuditLog.objects.all()[:50],
        },
    )
