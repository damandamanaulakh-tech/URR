"""Source-Domain Classifier (SB-03), made real — and a numeric audit.

The Core Gate's six lenses read *the human under a claim*. Pointed at a billing
spreadsheet they produce word-salad ("the Mask of cumulative bill amounts
conceals the Wound of prior over-claims"). That is a force-fit, and the core
forbids force-fitting (classify, don't reject; never present a guess as fact).

So before the engine picks a frame it must ask *what kind of source is this?*
A numeric/financial document is **audited** (totals, GST, corrections, what is
and isn't verifiable). Prose / a claim / a belief is read by the lenses. This
module does that split with zero dependencies, and the audit is computed in
Python — deterministic and testable — not guessed by a model.
"""

from __future__ import annotations

import re

# A number: optional accounting-negative (leading - or wrapping parens),
# thousands separators, optional decimals. Anchored so it won't eat parts of words.
_NUM_RE = re.compile(
    r"(?<![\w.])\(?-?\d{1,3}(?:,\d{3})+(?:\.\d+)?\)?"      # 1,234,567.8
    r"|(?<![\w.])\(?-?\d+(?:\.\d+)?\)?"                    # 1234.5 / -19048 / (209745)
)

# Words that mark a financial/billing document.
_FINANCIAL = (
    "amount", "invoice", "bill", "total", "subtotal", "qty", "quantity", "rate",
    "payable", "gst", "tax", "igst", "cgst", "sgst", "vat", "boq", "rs.", "rs ",
    "inr", "₹", "$", "cost", "price", "balance", "debit", "credit note",
)
_LABELS_TOTAL = ("grand total", "total amount", "amount payable", "net payable",
                 "net amount", "total", "amount")
_LABELS_GST = ("gst", "igst", "cgst", "sgst", "tax", "vat")


def _to_float(tok: str) -> float | None:
    """Parse a matched token (handles 1,234.5 / -19048 / (209745) accounting-negative)."""
    t = tok.strip()
    neg = t.startswith("-") or (t.startswith("(") and t.endswith(")"))
    t = t.strip("()").lstrip("-").replace(",", "")
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if neg else v


def _fmt(v: float) -> str:
    """Compact number for display: drop the trailing .0 on whole numbers."""
    return str(int(v)) if v == int(v) else f"{v:.2f}"


def classify_domain(text: str, origin: str = "chat") -> dict:
    """What kind of source is this? Returns the domain plus the two routing
    flags the engine needs:

      * ``audit_applicable`` — run the numeric audit, treat as a provided
        document (don't demand a live web source for a private file).
      * ``lens_applicable``  — read the human under the words with the six lenses.
    """
    low = text.lower()
    nums = _NUM_RE.findall(text)
    number_count = len(nums)
    digit_ratio = sum(c.isdigit() for c in text) / max(1, len(text))
    financial_hits = sum(1 for w in _FINANCIAL if w in low)
    looks_numeric = number_count >= 15 or digit_ratio > 0.08
    from_file = origin.startswith(("upload", "file"))

    if looks_numeric and (financial_hits >= 2 or "gst" in low):
        domain, label = "numeric_financial", "Numeric / financial document"
    elif looks_numeric and (number_count >= 25 or from_file):
        domain, label = "tabular", "Tabular / numeric data"
    else:
        domain, label = "prose", "Prose / claim / question"

    audit_applicable = domain in ("numeric_financial", "tabular")
    return {
        "domain": domain,
        "label": label,
        "audit_applicable": audit_applicable,
        "lens_applicable": not audit_applicable,
        "signals": {"numbers": number_count, "financial_terms": financial_hits,
                    "digit_ratio": round(digit_ratio, 3)},
    }


def _nearby(text: str, keyword: str, window: int = 56, limit: int = 6) -> list[float]:
    """The numbers that sit right next to a label (e.g. the figure after 'GST')."""
    low, out, start = text.lower(), [], 0
    while len(out) < limit:
        i = low.find(keyword, start)
        if i < 0:
            break
        m = _NUM_RE.search(text[i:i + window])
        if m:
            v = _to_float(m.group(0))
            if v is not None and v not in out:
                out.append(v)
        start = i + len(keyword)
    return out


def audit_numeric(text: str) -> dict:
    """A real, honest read of a numeric/financial document.

    It reports only what is observable from the flattened text — the figures
    present, the ones sitting next to total/GST labels, and the negative
    (correction) entries — and states plainly what it *cannot* certify without
    the structured sheet or the source contract. No force-fit, no fake fact.
    """
    values = [v for tok in _NUM_RE.findall(text) if (v := _to_float(tok)) is not None]
    negatives = [v for v in values if v < 0]
    candidate_total = max(values, key=abs) if values else None
    stated, seen = [], set()
    for kw in _LABELS_TOTAL:
        for v in _nearby(text, kw):
            if v not in seen and abs(v) >= 100:        # ignore tiny near-label noise
                seen.add(v); stated.append(v)
    gst = []
    for kw in _LABELS_GST:
        for v in _nearby(text, kw):
            if v not in gst:
                gst.append(v)

    caveats = [
        "Figures are read from the flattened sheet — line-item reconciliation "
        "needs the structured spreadsheet.",
        "Whether the rates/quantities are correct cannot be verified without the "
        "source contract / BOQ. This is a review of what the file states, not a "
        "certification that the bill is right.",
    ]
    summary = (f"{len(values)} numeric cells read"
               + (f"; largest figure {_fmt(candidate_total)} (likely the grand total)"
                  if candidate_total is not None else "")
               + (f"; {len(negatives)} negative/correction entr"
                  + ("y" if len(negatives) == 1 else "ies") if negatives else
                  "; no negative entries"))
    return {
        "number_count": len(values),
        "candidate_total": None if candidate_total is None else _fmt(candidate_total),
        "stated_totals": [_fmt(v) for v in stated[:6]],
        "gst_figures": [_fmt(v) for v in gst[:6]],
        "negative_count": len(negatives),
        "negative_examples": [_fmt(v) for v in negatives[:5]],
        "summary": summary,
        "caveats": caveats,
    }
