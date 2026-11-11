from xml.sax.saxutils import escape

from paydar_fixtures.model import Statement

OFX_HEADER = (
    '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
    '<?OFX OFXHEADER="200" VERSION="220" SECURITY="NONE" OLDFILEUID="NONE" NEWFILEUID="NONE"?>\n'
)
STATUS = "<STATUS><CODE>0</CODE><SEVERITY>INFO</SEVERITY></STATUS>"
SIGNON = f"<SIGNONMSGSRSV1><SONRS>{STATUS}<DTSERVER>20261001</DTSERVER><LANGUAGE>ENG</LANGUAGE></SONRS></SIGNONMSGSRSV1>\n"


def money(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    whole, frac = divmod(abs(cents), 100)
    return f"{sign}{whole}.{frac:02d}"


def to_csv(s: Statement) -> str:
    lines = ["Date,Description,Amount,Balance"]
    balance = s.opening_cents
    for t in s.txns:  # balance is bank-computed over true rows; omitted rows are not written
        balance += t.amount_cents
        if t not in s.omitted:
            lines.append(
                f'{t.post_date:%m/%d/%Y},"{t.description}",{money(t.amount_cents)},{money(balance)}'
            )
    return "\n".join(lines) + "\n"


def to_ofx(s: Statement) -> str:
    liability = s.account.account_class == "liability"
    sign = -1 if liability else 1  # OFX card convention: purchases and amounts owed are negative
    rows = "".join(
        f"<STMTTRN><TRNTYPE>{'CREDIT' if sign * t.amount_cents > 0 else 'DEBIT'}</TRNTYPE>"
        f"<DTPOSTED>{t.post_date:%Y%m%d}</DTPOSTED><TRNAMT>{money(sign * t.amount_cents)}</TRNAMT>"
        f"<FITID>{t.fitid}</FITID><NAME>{escape(t.description)}</NAME></STMTTRN>\n"
        for t in s.file_txns
    )
    tranlist = (
        f"<BANKTRANLIST><DTSTART>{s.period_start:%Y%m%d}</DTSTART><DTEND>{s.period_end:%Y%m%d}</DTEND>\n"
        f"{rows}</BANKTRANLIST>"
        f"<LEDGERBAL><BALAMT>{money(sign * s.closing_cents)}</BALAMT><DTASOF>{s.period_end:%Y%m%d}</DTASOF></LEDGERBAL>"
    )
    acct = s.account.ofx_acct_id
    if liability:
        body = (
            f"<CREDITCARDMSGSRSV1><CCSTMTTRNRS><TRNUID>1</TRNUID>{STATUS}<CCSTMTRS><CURDEF>USD</CURDEF>"
            f"<CCACCTFROM><ACCTID>{acct}</ACCTID></CCACCTFROM>\n{tranlist}"
            "</CCSTMTRS></CCSTMTTRNRS></CREDITCARDMSGSRSV1>\n"
        )
    else:
        body = (
            f"<BANKMSGSRSV1><STMTTRNRS><TRNUID>1</TRNUID>{STATUS}<STMTRS><CURDEF>USD</CURDEF>"
            f"<BANKACCTFROM><BANKID>123456789</BANKID><ACCTID>{acct}</ACCTID><ACCTTYPE>CHECKING</ACCTTYPE>"
            f"</BANKACCTFROM>\n{tranlist}</STMTRS></STMTTRNRS></BANKMSGSRSV1>\n"
        )
    return f"{OFX_HEADER}<OFX>{SIGNON}{body}</OFX>\n"
