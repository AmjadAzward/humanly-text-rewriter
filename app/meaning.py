"""Model-free meaning check: flags original sentences whose key terms mostly vanished from the rewrite."""
import re

STOP = set("""about above after again against also because been before being below between both but could does doing down during each
from further have having here into just more most other over same should some such than that their them then there these they this
those through under until very was were what when where which while who whom will with would your you our out off only own too
can did for and are not the its it's has had her his she him how any all across several many much made make makes
now still often really quite rather another every though however""".split())


def _stem(word):
    word = word.lower()
    for suffix in ("ing", "ed", "es", "ly", "s"):
        if len(word) > 5 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def _terms(text):
    terms = set()
    for token in re.findall(r"[A-Za-z]+|\d[\d,.]*\d|\d", text):
        if token[0].isdigit():
            terms.add(token.rstrip(".,"))
        elif len(token) > 3 and token.lower() not in STOP:
            terms.add(_stem(token))
    return terms


def _present(term, rewritten_terms):
    if term in rewritten_terms:
        return True
    if term.isdigit() or term[0].isdigit():
        return False
    return any(other.startswith(term[:5]) or term.startswith(other[:5]) for other in rewritten_terms if len(other) >= 5 and len(term) >= 5)


def check_meaning(original, rewritten, threshold=0.5):
    """Return original sentences with low key-term coverage: [{sentence, coverage, missing}]."""
    rewritten_terms = _terms(rewritten)
    flagged = []
    for sentence in re.split(r"(?<=[.!?])\s+", original.strip()):
        sentence = sentence.strip()
        keys = _terms(sentence)
        if len(keys) < 3:
            continue
        missing = sorted(t for t in keys if not _present(t, rewritten_terms))
        coverage = 1 - len(missing) / len(keys)
        if coverage < threshold:
            shown = {}
            for token in re.findall(r"[A-Za-z]+|\d[\d,.]*\d|\d", sentence):
                shown.setdefault(token.rstrip(".,") if token[0].isdigit() else _stem(token), token.rstrip(".,"))
            flagged.append({"sentence": sentence, "coverage": round(coverage * 100),
                            "missing": [shown.get(t, t) for t in missing][:6]})
    return flagged
