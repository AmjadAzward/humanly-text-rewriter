import os
import re
import requests
from .prompt import SYSTEM_PROMPT, build_user_prompt

CHUNK_WORDS = 220


class AIConfigurationError(Exception):
    pass


class AIRequestError(Exception):
    pass


def available_models():
    default = os.getenv("AI_MODEL", "qwen2.5:7b").strip()
    listed = [m.strip() for m in os.getenv("AI_MODELS", "").split(",") if m.strip()]
    return listed or [default]


def _chat(messages, model=None, max_tokens=None):
    # Works with any OpenAI-compatible chat API (Ollama, Groq, OpenRouter, OpenAI...).
    base_url = os.getenv("AI_BASE_URL", "http://127.0.0.1:11434/v1").strip().rstrip("/")
    api_key = os.getenv("AI_API_KEY", "ollama").strip()
    model = (model or os.getenv("AI_MODEL", "qwen2.5:7b")).strip()
    if not model:
        raise AIConfigurationError("Set AI_MODEL in the .env file, then restart the application.")
    payload = {"model": model, "messages": messages, "temperature": 0.8, "top_p": 0.9}
    if max_tokens:
        payload["max_tokens"] = int(max_tokens)
    try:
        response = requests.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=300,
        )
        if response.status_code >= 400:
            try:
                err = response.json().get("error", response.text)
                detail = err.get("message", err) if isinstance(err, dict) else err
            except ValueError:
                detail = response.text
            raise AIRequestError(f"AI service returned an error ({response.status_code}): {detail}")
        data = response.json()
        output = ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "")
        if not output or not output.strip():
            raise AIRequestError("The AI service returned an empty response. Please try again.")
        return output.strip()
    except requests.Timeout:
        raise AIRequestError("The request timed out. Please try again.")
    except requests.RequestException as exc:
        raise AIRequestError(f"Could not connect to the AI service: {exc}")


def _clean(output):
    """Strip tags, 'Here is...' preambles and wrapping quotes the model sometimes adds."""
    output = re.sub(r"</?(text|previous)>", "", output).strip()
    output = re.sub(r"^(here(['’]s| is)[^\n]*:|rewrite[d]?( text)?:|sure[^\n]*:)\s*", "", output, flags=re.I).strip()
    if len(output) > 1 and output[0] in "\"“" and output[-1] in "\"”" and output.count('"') + output.count("“") <= 2:
        output = output[1:-1].strip()
    return output


def _facts(text):
    """Numbers and URLs that must survive a rewrite."""
    found = set(re.findall(r"\d[\d,./%-]*\d|\d", text)) | set(re.findall(r"https?://\S+", text))
    found |= _names(text)
    return {x.rstrip(".,)") for x in found}


_ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
         "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
_TENS = {20: "twenty", 30: "thirty", 40: "forty", 50: "fifty", 60: "sixty", 70: "seventy", 80: "eighty", 90: "ninety"}


def _number_word(n):
    if n < 20:
        return _ONES[n]
    if n < 100:
        tens, ones = n - n % 10, n % 10
        return _TENS[tens] + (("-" + _ONES[ones]) if ones else "")
    return None


def _missing(need, output):
    """Facts from the original that are absent from the rewrite (spelled-out small numbers count as present)."""
    have = _facts(output)
    lowered = output.lower()
    missing = set()
    for fact in need - have:
        if fact.isdigit():
            word = _number_word(int(fact))
            if word and (word in lowered or word.replace("-", " ") in lowered):
                continue
        missing.add(fact)
    return missing


def _names(text):
    """Capitalised words that are not the first word of a sentence (likely names/brands)."""
    names = set()
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", text):
        words = re.findall(r"[A-Za-z][A-Za-z'’-]*", sentence)
        for word in words[1:]:
            if len(word) > 2 and word[0].isupper() and not word.isupper():
                names.add(word)
    return names


def _sentence_count(text):
    return len([s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()])


def _split_chunks(text):
    """Group paragraphs into chunks of about CHUNK_WORDS words; split very long paragraphs by sentence."""
    pieces = []
    for para in re.split(r"(\n\s*\n)", text):
        if para.strip() and len(para.split()) > CHUNK_WORDS * 1.5:
            sentences = re.split(r"(?<=[.!?])\s+", para)
            buf, count = [], 0
            for sent in sentences:
                buf.append(sent)
                count += len(sent.split())
                if count >= CHUNK_WORDS:
                    pieces.append(" ".join(buf) + " ")
                    buf, count = [], 0
            if buf:
                pieces.append(" ".join(buf))
        else:
            pieces.append(para)
    chunks, current, count = [], "", 0
    for piece in pieces:
        current += piece
        count += len(piece.split())
        if count >= CHUNK_WORDS and piece.strip():
            chunks.append(current)
            current, count = "", 0
    if current.strip():
        chunks.append(current)
    return chunks or [text]


def _rewrite_chunk(chunk, tone, strength, previous, model=None):
    lead = re.match(r"\s*", chunk).group(0)
    trail = re.search(r"\s*$", chunk).group(0)
    body = chunk.strip()
    if not body:
        return chunk, None
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(body, tone, strength, previous)},
    ]
    need = _facts(body)
    best = None
    for _ in range(2):
        out = _clean(_chat(messages, model, max_tokens=int(len(body.split()) * 2.2) + 80))
        lost = _missing(need, out)
        missing = len(lost)
        too_short = len(body.split()) > 25 and len(out.split()) < 0.45 * len(body.split())
        before, after = _sentence_count(body), _sentence_count(out)
        dropped = before >= 3 and after < 0.6 * before
        if not missing and not too_short and not dropped:
            return lead + out + trail, None
        score = missing + (100 if too_short else 0) + (50 if dropped else 0)
        if best is None or score < best[0]:
            best = (score, out, sorted(lost)[:5], too_short or dropped)
    notes = []
    if best[2]:
        notes.append("could not confirm these details were kept: " + ", ".join(best[2]))
    if best[3]:
        notes.append("some sentences may have been dropped or merged")
    return lead + best[1] + trail, "; ".join(notes)


def keep_model_warm(model=None):
    """Ask a local Ollama server to keep the model in memory so the next rewrite skips the reload."""
    base_url = os.getenv("AI_BASE_URL", "http://127.0.0.1:11434/v1").strip().rstrip("/")
    if "11434" not in base_url:
        return
    try:
        requests.post(base_url[:-3] + "/api/generate",
                      json={"model": model or os.getenv("AI_MODEL", "qwen2.5:7b"), "keep_alive": "60m"}, timeout=10)
    except requests.RequestException:
        pass


def rewrite_iter(text, tone, strength, previous_text="", model=None):
    """Yield (number, total, rewritten_chunk, note) as each chunk finishes."""
    chunks = _split_chunks(text)
    previous = previous_text
    for number, chunk in enumerate(chunks, 1):
        rewritten, note = _rewrite_chunk(chunk, tone, strength, previous, model)
        yield number, len(chunks), rewritten, note
        previous = rewritten.strip()[-600:]
    keep_model_warm(model)


def rewrite_text(text, tone, strength, previous_text="", model=None):
    """Returns (rewritten_text, warnings) where warnings is a list of strings."""
    results, warnings = [], []
    for number, _total, rewritten, note in rewrite_iter(text, tone, strength, previous_text, model):
        results.append(rewritten)
        if note:
            warnings.append(f"Section {number}: {note}.")
    return "".join(results).strip(), warnings
