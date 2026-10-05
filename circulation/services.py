"""Circulation business rules. Every attempt (allowed or denied) is stored as a Transaction and audited."""
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from catalog.models import Item
from circulation.models import Fine, Loan, Transaction
from core import audit, config
from members.models import Member


class CirculationError(Exception):
    def __init__(self, code, message, item=None, member_no=""):
        super().__init__(message)
        self.code, self.message, self.item, self.member_no = code, message, item, member_no


def find_item(identifier):
    """Resolve an item by barcode, accession number or RFID tag UID."""
    ident = (identifier or "").strip()
    item = Item.objects.select_related("biblio").filter(barcode=ident).first()
    if item is None:
        item = Item.objects.select_related("biblio").filter(accession_no=ident).first()
    if item is None:
        item = Item.objects.select_related("biblio").filter(tag__tag_uid=ident.upper()).first()
    return item


def _record(tx_type, channel, operator, item, item_ref, member_no, success, reason="", detail=""):
    Transaction.objects.create(
        tx_type=tx_type, channel=channel, item=item, item_ref=item_ref[:60], member_no=member_no[:30],
        operator=str(getattr(operator, "username", operator))[:150], success=success, reason=reason, detail=detail[:250],
    )
    audit.log(operator, f"{tx_type}_{'OK' if success else 'DENIED'}", item_ref, f"member={member_no} {reason} {detail}")


def _deny(tx_type, channel, operator, item, item_ref, member_no, code, message):
    """Raise a denial. The caller's wrapper records it OUTSIDE the rolled-back transaction."""
    raise CirculationError(code, message, item=item, member_no=member_no)


def _guarded(tx_type, channel, operator, ident, member_no, fn):
    try:
        with transaction.atomic():
            return fn()
    except CirculationError as err:
        _record(tx_type, channel, operator, err.item, ident, err.member_no or member_no, False, err.code, err.message)
        raise


def _check_member(tx_type, channel, operator, item, ref, member_no):
    member = Member.objects.filter(member_no=member_no).first()
    if member is None or not member.active:
        _deny(tx_type, channel, operator, item, ref, member_no, "MEMBER_NOT_FOUND", "Member not found or inactive.")
    if member.is_blocked:
        _deny(tx_type, channel, operator, item, ref, member_no, "MEMBER_BLOCKED", member.block_reason or "Member is blocked.")
    owed = Decimal(member.outstanding_fines())
    limit = config.get_decimal("FINE_LIMIT")
    if owed > limit:
        _deny(tx_type, channel, operator, item, ref, member_no, "FINE_LIMIT_EXCEEDED", f"Outstanding fines {owed} exceed the limit {limit}.")
    return member


def _set_security(item, secured):
    try:
        tag = item.tag
    except Exception:
        tag = None
    if tag is not None:
        tag.security_bit = secured
        tag.save(update_fields=["security_bit"])


def checkout(identifier, member_no, operator, channel="WEB"):
    return _guarded("CHECKOUT", channel, operator, identifier, member_no,
                    lambda: _checkout(identifier, member_no, operator, channel))


def _checkout(identifier, member_no, operator, channel):
    item = find_item(identifier)
    if item is None:
        _deny("CHECKOUT", channel, operator, None, identifier, member_no, "ITEM_NOT_FOUND", "Item not found.")
    member = _check_member("CHECKOUT", channel, operator, item, identifier, member_no)
    if item.is_reference:
        _deny("CHECKOUT", channel, operator, item, identifier, member_no, "REFERENCE_ITEM", "Reference items cannot be borrowed.")
    if item.status != Item.Status.AVAILABLE:
        _deny("CHECKOUT", channel, operator, item, identifier, member_no, "NOT_AVAILABLE", f"Item is {item.get_status_display().lower()}.")
    now = timezone.now()
    loan = Loan.objects.create(item=item, member=member, out_at=now, due_at=now + timedelta(days=config.get_int("LOAN_DAYS")))
    item.status = Item.Status.ON_LOAN
    item.save(update_fields=["status"])
    _set_security(item, False)
    _record("CHECKOUT", channel, operator, item, identifier, member_no, True, detail=f"due {loan.due_at:%Y-%m-%d}")
    return loan


def checkin(identifier, operator, channel="WEB"):
    return _guarded("CHECKIN", channel, operator, identifier, "",
                    lambda: _checkin(identifier, operator, channel))


def _checkin(identifier, operator, channel):
    item = find_item(identifier)
    if item is None:
        _deny("CHECKIN", channel, operator, None, identifier, "", "ITEM_NOT_FOUND", "Item not found.")
    loan = Loan.objects.filter(item=item, returned_at__isnull=True).select_related("member").first()
    if loan is None:
        _deny("CHECKIN", channel, operator, item, identifier, "", "NOT_ON_LOAN", "Item is not on loan.")
    now = timezone.now()
    loan.returned_at = now
    loan.save(update_fields=["returned_at"])
    late_days = max((now.date() - loan.due_at.date()).days, 0)
    fine = None
    if late_days:
        amount = config.get_decimal("FINE_PER_DAY") * late_days
        fine = Fine.objects.create(member=loan.member, loan=loan, amount=amount, reason=f"Overdue {late_days} day(s)")
    item.status = Item.Status.AVAILABLE
    item.save(update_fields=["status"])
    _set_security(item, True)
    _record("CHECKIN", channel, operator, item, identifier, loan.member.member_no, True, detail=f"fine {fine.amount}" if fine else "")
    return loan, fine


def renew(identifier, operator, channel="WEB"):
    return _guarded("RENEW", channel, operator, identifier, "",
                    lambda: _renew(identifier, operator, channel))


def _renew(identifier, operator, channel):
    item = find_item(identifier)
    if item is None:
        _deny("RENEW", channel, operator, None, identifier, "", "ITEM_NOT_FOUND", "Item not found.")
    loan = Loan.objects.filter(item=item, returned_at__isnull=True).select_related("member").first()
    if loan is None:
        _deny("RENEW", channel, operator, item, identifier, "", "NOT_ON_LOAN", "Item is not on loan.")
    _check_member("RENEW", channel, operator, item, identifier, loan.member.member_no)
    if loan.renewals >= config.get_int("MAX_RENEWALS"):
        _deny("RENEW", channel, operator, item, identifier, loan.member.member_no, "RENEWAL_LIMIT", "Maximum renewals reached.")
    loan.renewals += 1
    loan.due_at = loan.due_at + timedelta(days=config.get_int("RENEW_DAYS"))
    loan.save(update_fields=["renewals", "due_at"])
    _record("RENEW", channel, operator, item, identifier, loan.member.member_no, True, detail=f"due {loan.due_at:%Y-%m-%d}")
    return loan


def due_date(identifier):
    item = find_item(identifier)
    if item is None:
        raise CirculationError("ITEM_NOT_FOUND", "Item not found.")
    loan = Loan.objects.filter(item=item, returned_at__isnull=True).select_related("member").first()
    if loan is None:
        raise CirculationError("NOT_ON_LOAN", "Item is not on loan.")
    return loan


@transaction.atomic
def pay_fines(member_no, operator):
    member = Member.objects.get(member_no=member_no)
    total = Decimal(member.outstanding_fines())
    member.fines.filter(paid=False).update(paid=True)
    audit.log(operator, "FINES_PAID", member_no, f"amount={total}")
    return total
