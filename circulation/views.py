from django.contrib import messages
from django.shortcuts import redirect, render

from circulation import services
from circulation.models import Transaction
from core.roles import require_perm


@require_perm("circ.process")
def desk(request):
    if request.method == "POST":
        action = request.POST.get("action")
        ident = request.POST.get("item", "").strip()
        member_no = request.POST.get("member_no", "").strip()
        try:
            if action == "checkout":
                loan = services.checkout(ident, member_no, request.user)
                messages.success(request, f"Checked out {loan.item.biblio.title} to {loan.member.name}. Due {loan.due_at:%d %b %Y}.")
            elif action == "checkin":
                loan, fine = services.checkin(ident, request.user)
                extra = f" Fine of {fine.amount} added." if fine else ""
                messages.success(request, f"Checked in {loan.item.biblio.title}.{extra}")
            elif action == "renew":
                loan = services.renew(ident, request.user)
                messages.success(request, f"Renewed. New due date {loan.due_at:%d %b %Y}.")
            elif action == "due":
                loan = services.due_date(ident)
                messages.info(request, f"{loan.item.biblio.title} is due {loan.due_at:%d %b %Y} (borrower {loan.member.member_no}).")
        except services.CirculationError as err:
            messages.error(request, f"Not allowed: {err.message} [{err.code}]")
        return redirect("desk")
    recent = Transaction.objects.all()[:15]
    return render(request, "circulation/desk.html", {"recent": recent})
