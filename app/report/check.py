"""Check that every number in the AI text appears in the facts.

A number in the text is accepted when:
- it equals a number found anywhere in the facts (numeric values, and
  numbers inside text values such as records "9-5", streaks "W 3" and
  reason lines), ignoring the sign, because the text says "3.4 below his
  norm" for a value of -3.4;
- it is a small count from 1 to 5 ("three keys", "his top 3 options");
- it is 100, the unit in "per 100";
- it is part of a date or season label in the facts: "Nov 17" or "17" for
  2026-11-17, the year 2026, or "2025-26".
Anything else is flagged with the section it came from.
"""

import re
from datetime import date

ALWAYS_OK = {1.0, 2.0, 3.0, 4.0, 5.0, 100.0}
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]

# A number, optionally a hyphen-joined pair (9-5, 2025-26), optionally a %.
TOKEN = re.compile(r"(?<![\w.])[+\-−]?\d+(?:\.\d+)?(?:-\d+(?:\.\d+)?)?%?")
DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
SEASON = re.compile(r"\b(\d{4})-(\d{2})\b")
MONTH_DAY = re.compile(r"\b(" + "|".join(m[:3] for m in MONTHS) + r")[a-z]*\.?\s+(\d{1,2})\b")


def _value(text):
    return abs(float(text.replace("−", "-").lstrip("+-").rstrip("%")))


def facts_vocabulary(facts):
    """All numbers, date parts and season labels the facts allow."""
    numbers, labels, month_days = set(), set(), set()

    def walk(v):
        if isinstance(v, bool) or v is None:
            return
        if isinstance(v, (int, float)):
            numbers.add(round(abs(float(v)), 6))
        elif isinstance(v, str):
            for y, m, d in DATE.findall(v):
                when = date(int(y), int(m), int(d))
                month_days.add((MONTHS[when.month - 1][:3], when.day))
                numbers.update({float(when.year), float(when.day)})
                labels.add(f"{y}-{m}-{d}")
            for start, end in SEASON.findall(v):
                labels.add(f"{start}-{end}")
                numbers.update({float(start)})
            for tok in TOKEN.findall(v):
                for part in tok.rstrip("%").replace("−", "-").lstrip("+-").split("-"):
                    if part:
                        numbers.add(round(float(part), 6))
                labels.add(tok.lstrip("+-−").rstrip("%"))
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, (list, tuple)):
            for x in v:
                walk(x)

    walk(facts)
    return numbers, labels, month_days


def check_text(text, vocab):
    """Return the numbers in text that the facts do not support."""
    numbers, labels, month_days = vocab
    # Dates written as "Nov 17" are fine when that date is in the facts.
    skip_spans = []
    for m in MONTH_DAY.finditer(text):
        if (m.group(1), int(m.group(2))) in month_days:
            skip_spans.append(m.span(2))
    bad = []
    for m in TOKEN.finditer(text):
        if any(a <= m.start() < b for a, b in skip_spans):
            continue
        tok = m.group(0)
        core = tok.lstrip("+-−").rstrip("%")
        if core in labels:
            continue
        parts = [p for p in core.split("-") if p]
        if all(_value(p) in numbers or _value(p) in ALWAYS_OK for p in parts):
            continue
        start = max(0, m.start() - 40)
        bad.append({"number": tok, "context": text[start:m.end() + 40].strip()})
    return bad


def check_sections(sections, facts):
    """Flags for every section of the report: [{section, item, number, context}]."""
    vocab = facts_vocabulary(facts)
    flags = []

    def add(section, item, text):
        for f in check_text(text or "", vocab):
            flags.append({"section": section, "item": item, **f})

    add("Opponent identity", None, sections.get("opponent_identity"))
    for i, k in enumerate(sections.get("keys_to_the_game", []), start=1):
        add("Keys to the game", i, f"{k.get('title', '')}. {k.get('detail', '')}")
    for i, p in enumerate(sections.get("players_to_watch", []), start=1):
        add("Players to watch", i, p.get("note"))
    for i, n in enumerate(sections.get("matchup_notes", []), start=1):
        add("Matchup notes", i, n.get("note"))
    return flags
