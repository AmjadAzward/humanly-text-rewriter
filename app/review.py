"""Instant, model-free review that flags stiff or generic phrasing so the writer can fix it by hand."""
import re

# (regex, reason, suggestion)
PHRASES = [
    (r"it(?:'|’)?s (?:important|worth|crucial) to (?:note|mention|remember)", "Throat-clearing that adds nothing.", "Just state the point."),
    (r"it is (?:important|worth|crucial) to (?:note|mention|remember)", "Throat-clearing that adds nothing.", "Just state the point."),
    (r"in today(?:'|’)?s (?:fast-paced|digital|modern|ever-changing)[\w\s-]{0,20}", "Stock opener used everywhere.", "Open with a specific fact or example."),
    (r"\bdelve(?:s|d)? (?:into|deeper)", "Overused word.", "Use 'look at', 'explore' or 'dig into'."),
    (r"\bmoreover\b", "Formal connector that reads stiff.", "Use 'also', 'and', or start a new sentence."),
    (r"\bfurthermore\b", "Formal connector that reads stiff.", "Use 'also' or 'and'."),
    (r"\badditionally\b", "Formal connector that reads stiff.", "Use 'also', or drop it."),
    (r"\bin conclusion\b", "Announces the ending instead of just ending.", "Cut it and land the last point."),
    (r"\bin summary\b", "Announces the ending instead of just ending.", "Cut it and land the last point."),
    (r"\ba testament to\b", "Cliche.", "Say what it shows, plainly."),
    (r"\bplays? a (?:crucial|vital|pivotal|key|significant) role\b", "Vague and inflated.", "Say what it actually does."),
    (r"\bunlock(?:s|ing)? the (?:full )?potential\b", "Marketing cliche.", "Name the concrete benefit."),
    (r"\bnavigat(?:e|es|ing) the (?:complex )?(?:landscape|world|waters)\b", "Cliche.", "Say what is actually being dealt with."),
    (r"\bgame[- ]changer\b", "Hype.", "Describe the change itself."),
    (r"\bseamless(?:ly)?\b", "Hype word.", "Say how it works or drop it."),
    (r"\bleverag(?:e|es|ed|ing)\b", "Jargon.", "Use 'use'."),
    (r"\butiliz(?:e|es|ed|ing)\b", "Stiff.", "Use 'use'."),
    (r"\bfacilitat(?:e|es|ed|ing)\b", "Stiff.", "Use 'help' or 'make easier'."),
    (r"\bcomprehensive\b", "Vague filler.", "Say what it covers."),
    (r"\bholistic\b", "Vague filler.", "Say what it includes."),
    (r"\brobust\b", "Vague filler.", "Say how it is strong."),
    (r"\bcutting-edge\b", "Hype.", "Say what is new about it."),
    (r"\bever-evolving\b", "Cliche.", "Name what is changing."),
    (r"\btapestry\b", "Overused metaphor.", "Use a plain word."),
    (r"\bat the end of the day\b", "Filler.", "Cut it."),
    (r"\bin order to\b", "Wordy.", "Use 'to'."),
    (r"\bdue to the fact that\b", "Wordy.", "Use 'because'."),
    (r"\bit goes without saying\b", "Then do not say it.", "Cut it."),
    (r"\bonly time will tell\b", "Cliche ending.", "Cut it."),
    (r"\bwhether you(?:'|’)?re a [\w\s]+ or a [\w\s]+", "Formulaic audience line.", "Speak to one specific reader."),
]

_COMPILED = [(re.compile(p, re.I), why, fix) for p, why, fix in PHRASES]


def review_text(text):
    """Return a list of findings: {phrase, reason, suggestion, count}."""
    findings = []
    seen = {}
    for pattern, why, fix in _COMPILED:
        for match in pattern.finditer(text):
            key = match.group(0).strip().lower()
            if key in seen:
                seen[key]["count"] += 1
                continue
            item = {"phrase": match.group(0).strip(), "reason": why, "suggestion": fix, "count": 1}
            seen[key] = item
            findings.append(item)

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    long_ones = [s for s in sentences if len(s.split()) > 40]
    for sentence in long_ones[:3]:
        findings.append({"phrase": sentence[:70].rstrip() + "...", "reason": f"Very long sentence ({len(sentence.split())} words).",
                         "suggestion": "Split it into two or three sentences.", "count": 1})

    lengths = [len(s.split()) for s in sentences]
    if len(lengths) >= 6:
        mean = sum(lengths) / len(lengths)
        spread = (sum((n - mean) ** 2 for n in lengths) / len(lengths)) ** 0.5
        if mean > 0 and spread / mean < 0.25:
            findings.append({"phrase": "Sentence rhythm", "count": 1,
                             "reason": f"Most sentences are about {round(mean)} words long, which reads monotone.",
                             "suggestion": "Mix in a few short sentences and let one run longer."})

    openers = {}
    for sentence in sentences:
        words = sentence.split()[:2]
        if len(words) == 2:
            openers.setdefault(" ".join(words).lower(), 0)
            openers[" ".join(words).lower()] += 1
    for opener, count in openers.items():
        if count >= 3:
            findings.append({"phrase": opener.capitalize() + " ...", "reason": f"{count} sentences start the same way.",
                             "suggestion": "Vary how sentences begin.", "count": count})
    return findings
