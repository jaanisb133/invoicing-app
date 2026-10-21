"""The one rule every document total follows.

An e-invoice (EN 16931 / PEPPOL BIS Billing 3.0) is checked line by line: each
line is rounded to the cent, the document net is the sum of those rounded
lines, and the VAT is that net times the rate, rounded once. The PDF, the HTML
previews, the lists, the dashboard and the XML all have to show the same
figures, so they all come from here (and from vrRound2 in base.html, its
JavaScript twin). Rounding is half-up, away from zero, on the decimal value:
1,005 → 1,01, never the binary float's 1,00.

Documents keep their totals in documents.subtotal / vat_amount / rounding /
total, written on every save. Documents saved before this rule existed were
backfilled with the totals they had always shown, so nothing already issued
changes by a cent.
"""

from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")
ZERO = Decimal("0")


def dec(value) -> Decimal:
    """A Decimal holding the value as written: 0.1 is 0.1, not 0.1000000000000000055."""
    if isinstance(value, Decimal):
        return value
    if value is None or value == "":
        return ZERO
    return Decimal(str(value))


def cents(value) -> Decimal:
    return dec(value).quantize(CENT, rounding=ROUND_HALF_UP)


def line_total(quantity, price, included=False) -> Decimal:
    """A line's amount: quantity × price, rounded to the cent. "Included in the
    price" lines print without an amount and add nothing."""
    if included:
        return ZERO
    return cents(dec(quantity) * dec(price))


def vat_of(net, rate) -> Decimal:
    return cents(dec(net) * dec(rate) / 100)


def document_totals(items, vat_rate, rounding=0) -> dict:
    """{'lines': [Decimal per item], 'subtotal', 'vat', 'rounding', 'total'}.

    items are dicts with quantity, price_per_unit and an optional
    included_in_price flag. rounding is a cent-level adjustment to the amount
    payable (EN 16931 BT-114), used only where a VAT-inclusive price cannot be
    reached with a two-decimal net (subscription invoices: 1,99 € at 21 %).
    """
    lines = [line_total(i.get("quantity", 0), i.get("price_per_unit", 0),
                        bool(i.get("included_in_price")))
             for i in items]
    subtotal = sum(lines, ZERO)
    vat = vat_of(subtotal, vat_rate or 0)
    adjust = cents(rounding)
    return {"lines": lines, "subtotal": subtotal, "vat": vat,
            "rounding": adjust, "total": subtotal + vat + adjust}


def net_for_gross(gross, vat_rate):
    """(net, rounding) such that net + VAT(net) + rounding == gross, with net in
    cents and rounding as small as possible (0 whenever the gross is reachable).

    At 21 %, 1,99 € has no two-decimal net (1,64 → 1,98; 1,65 → 2,00), so it
    comes back as (1,64, 0,01).
    """
    gross = cents(gross)
    rate = dec(vat_rate or 0)
    guess = cents(gross / (1 + rate / 100))
    best = None
    for step in range(-3, 4):
        net = guess + CENT * step
        diff = gross - (net + vat_of(net, rate))
        key = (abs(diff), diff < 0)  # prefer exact, then a positive adjustment
        if best is None or key < best[0]:
            best = (key, net, diff)
    return best[1], best[2]
