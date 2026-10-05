"""NCIP 2.0 adapter (subset: LookupUser, LookupItem, CheckOutItem, CheckInItem, RenewItem).
MOCK/BOUNDARY implementation - NOT certified. Real vendor endpoints would replace the service calls."""
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

from circulation import services
from members.models import Member

NS = "http://www.niso.org/2008/ncip"


def _local(tag):
    return tag.split("}", 1)[-1]


def _text(root, name):
    for el in root.iter():
        if _local(el.tag) == name:
            return (el.text or "").strip()
    return ""


def _wrap(inner):
    return f'<?xml version="1.0" encoding="UTF-8"?><NCIPMessage xmlns="{NS}">{inner}</NCIPMessage>'


def _problem(op, code, detail):
    return _wrap(f"<{op}Response><Problem><ProblemType>{escape(code)}</ProblemType>"
                 f"<ProblemDetail>{escape(detail)}</ProblemDetail></Problem></{op}Response>")


def handle(xml_text, operator="ncip-client"):
    if "<!DOCTYPE" in xml_text.upper() or "<!ENTITY" in xml_text.upper():
        return _problem("Unknown", "Invalid Message Syntax", "DTD/entities are not accepted")
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return _problem("Unknown", "Invalid Message Syntax", "XML could not be parsed")
    children = [c for c in root if True]
    if not children:
        return _problem("Unknown", "Invalid Message Syntax", "Empty NCIPMessage")
    op = _local(children[0].tag)
    user, item = _text(children[0], "UserIdentifierValue"), _text(children[0], "ItemIdentifierValue")
    try:
        if op == "CheckOutItem":
            loan = services.checkout(item, user, operator, channel="NCIP")
            return _wrap(f"<CheckOutItemResponse><ItemId><ItemIdentifierValue>{escape(item)}</ItemIdentifierValue></ItemId>"
                         f"<UserId><UserIdentifierValue>{escape(user)}</UserIdentifierValue></UserId>"
                         f"<DateDue>{loan.due_at:%Y-%m-%dT%H:%M:%S}Z</DateDue></CheckOutItemResponse>")
        if op == "CheckInItem":
            loan, fine = services.checkin(item, operator, channel="NCIP")
            return _wrap(f"<CheckInItemResponse><ItemId><ItemIdentifierValue>{escape(item)}</ItemIdentifierValue></ItemId>"
                         f"<UserId><UserIdentifierValue>{escape(loan.member.member_no)}</UserIdentifierValue></UserId>"
                         f"</CheckInItemResponse>")
        if op == "RenewItem":
            loan = services.renew(item, operator, channel="NCIP")
            return _wrap(f"<RenewItemResponse><ItemId><ItemIdentifierValue>{escape(item)}</ItemIdentifierValue></ItemId>"
                         f"<DateForReturn>{loan.due_at:%Y-%m-%dT%H:%M:%S}Z</DateForReturn></RenewItemResponse>")
        if op == "LookupUser":
            m = Member.objects.filter(member_no=user).first()
            if not m:
                return _problem(op, "Unknown User", "No such user")
            return _wrap(f"<LookupUserResponse><UserId><UserIdentifierValue>{escape(user)}</UserIdentifierValue></UserId>"
                         f"<NameInformation>{escape(m.name)}</NameInformation><BlockOrTrap>{'true' if m.is_blocked else 'false'}</BlockOrTrap>"
                         f"<OutstandingFines>{m.outstanding_fines()}</OutstandingFines></LookupUserResponse>")
        if op == "LookupItem":
            it = services.find_item(item)
            if not it:
                return _problem(op, "Unknown Item", "No such item")
            return _wrap(f"<LookupItemResponse><ItemId><ItemIdentifierValue>{escape(item)}</ItemIdentifierValue></ItemId>"
                         f"<Title>{escape(it.biblio.title)}</Title><CirculationStatus>{it.status}</CirculationStatus></LookupItemResponse>")
    except services.CirculationError as err:
        return _problem(op, err.code, err.message)
    return _problem(op, "Unsupported Service", f"{op} is not implemented in this mock")
