from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from core import audit
from core.roles import has_perm, require_perm
from members.models import Member


@require_perm("members.view")
def member_list(request):
    if request.method == "POST":
        if not has_perm(request.user, "members.edit"):
            return redirect("members")
        action = request.POST.get("action")
        if action == "add":
            no, name = request.POST.get("member_no", "").strip(), request.POST.get("name", "").strip()
            if not no or not name:
                messages.error(request, "Member number and name are required.")
            elif Member.objects.filter(member_no=no).exists():
                messages.error(request, "That member number already exists.")
            else:
                Member.objects.create(member_no=no[:30], name=name[:150], email=request.POST.get("email", "")[:150],
                                      phone=request.POST.get("phone", "")[:30])
                audit.log(request.user, "MEMBER_CREATED", no, name)
                messages.success(request, f"Member {no} created.")
        else:
            member = get_object_or_404(Member, pk=request.POST.get("member_id"))
            if action == "block":
                member.is_blocked, member.block_reason = True, request.POST.get("reason", "Blocked by staff")[:200]
                member.save()
                audit.log(request.user, "MEMBER_BLOCKED", member.member_no, member.block_reason)
            elif action == "unblock":
                member.is_blocked, member.block_reason = False, ""
                member.save()
                audit.log(request.user, "MEMBER_UNBLOCKED", member.member_no)
            elif action == "pay":
                from circulation.services import pay_fines

                paid = pay_fines(member.member_no, request.user)
                messages.success(request, f"Recorded payment of {paid} for {member.member_no}.")
            elif action == "print_card":
                from rfid.adapters import get_adapter

                path = get_adapter("printer").print_text(f"card_{member.member_no}", f"LIBRARY CARD\n{member.name}\n{member.member_no}\n{member.category}")
                audit.log(request.user, "CARD_PRINTED", member.member_no, path)
                messages.success(request, f"Patron card sent to print spool for {member.member_no}.")
        return redirect("members")
    q = request.GET.get("q", "").strip()
    qs = Member.objects.all()
    if q:
        qs = qs.filter(Q(member_no__icontains=q) | Q(name__icontains=q))
    rows = [{"m": m, "fines": m.outstanding_fines()} for m in qs[:100]]
    return render(request, "members/list.html", {"rows": rows, "q": q})
