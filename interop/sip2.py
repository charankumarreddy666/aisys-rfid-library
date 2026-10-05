"""SIP2 adapter boundary (subset: 11 checkout, 09 checkin, 29 renew). MOCK - not certified."""
from datetime import datetime

from circulation import services

FIXED = {"11": 40, "09": 39, "29": 40}


def _fields(text, n):
    return {p[:2]: p[2:] for p in text[n:].split("|") if len(p) >= 2}


def _stamp():
    return datetime.now().strftime("%Y%m%d    %H%M%S")


def handle(message, operator="sip2-client"):
    msg = message.strip("\r\n")
    code = msg[:2]
    if code not in FIXED:
        return "96"  # request SC resend
    f = _fields(msg, FIXED[code])
    item, patron = f.get("AB", ""), f.get("AA", "")
    inst = f.get("AO", "")
    try:
        if code == "11":
            loan = services.checkout(item, patron, operator, channel="SIP2")
            return (f"121NNY{_stamp()}AO{inst}|AA{patron}|AB{item}|AJ{loan.item.biblio.title}|"
                    f"AH{loan.due_at:%Y%m%d    %H%M%S}|AFOK|")
        if code == "09":
            loan, fine = services.checkin(item, operator, channel="SIP2")
            return f"101YNN{_stamp()}AO{inst}|AB{item}|AQ{loan.item.shelf_location}|AA{loan.member.member_no}|AFOK|"
        loan = services.renew(item, operator, channel="SIP2")
        return (f"300NNY{_stamp()}AO{inst}|AA{loan.member.member_no}|AB{item}|AJ{loan.item.biblio.title}|"
                f"AH{loan.due_at:%Y%m%d    %H%M%S}|AFOK|")
    except services.CirculationError as err:
        resp = {"11": "120NUN", "09": "100NUN", "29": "300NUN"}[code]
        return f"{resp}{_stamp()}AO{inst}|AA{patron}|AB{item}|AF{err.message}|AG{err.code}|"
