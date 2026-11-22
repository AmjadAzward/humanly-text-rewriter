<div align="center">

<img src="app/static/favicon.svg" alt="Humanly logo" width="96" height="96">

# Humanly

### Make your writing sound like you.

Rewrite text in a natural, human voice. Keep your meaning. See exactly what changed.<br>
Runs fully on your own machine with a free local AI.

<br>

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.x-000000?style=for-the-badge&logo=flask&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-Local-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-Local_AI-6366F1?style=for-the-badge)
![Cost](https://img.shields.io/badge/Cost-Free-10B981?style=for-the-badge)
![Privacy](https://img.shields.io/badge/Data-Stays_Local-06B6D4?style=for-the-badge)

</div>

---

## Why Humanly

| | |
|---|---|
| ![](https://img.shields.io/badge/-Private-06B6D4) | Your text never leaves your computer. No accounts, no API keys, no billing. |
| ![](https://img.shields.io/badge/-Accurate-10B981) | Numbers, URLs and names are checked after every rewrite, with automatic retries. |
| ![](https://img.shields.io/badge/-Transparent-F59E0B) | Changed words are highlighted and counted, so you can review every edit. |
| ![](https://img.shields.io/badge/-Flexible-6366F1) | Seven tones, three strengths, and any OpenAI-compatible model. |

---

## Features

### Rewriting
- **7 tones:** Natural, Professional, Friendly, Casual, Academic, Persuasive, Concise
- **Rewrite levels:** Quality (light), Balanced (medium), Max (strong), plus Proofread only
- **Writing levels:** Default, Simpler, General audience, Advanced
- **Match my voice:** paste a sample of your own writing and rewrites follow your sentence style and word choice
- **Review phrasing:** instant, model-free check that flags stiff phrases, very long sentences, repeated openers and monotone rhythm so you can fix them by hand
- **Previous section field** so new text flows from what came before
- **Model switch** between a fast model and a higher quality one
- **Regenerate** for a fresh take, **Cancel** for long jobs, **Ctrl+Enter** to run

### Accuracy
- Long texts are processed in chunks of about 220 words
- Numbers, URLs and capitalized names are verified, and spelled-out numbers count as kept
- A separate model review checks claims, negation, dates, conditions, and unsupported additions; detected issues get one repair attempt
- Light, Medium, and Strong rewrites are retried and flagged when they stay too close to the source
- A warning banner appears if a rewrite cannot be fully verified. Model checks can still miss errors, so review important text.

### Review
- Word-level diff with highlighted changes and a "X of Y words changed" count
- **Compare** shows the original beside the rewrite, and **Check meaning** flags original sentences whose key terms mostly disappeared (no model needed; synonyms can cause false flags)
- Copy, export to `.txt`, import `.txt`, and chain rewrites with "Use as new input"
- History of the last 50 rewrites stored in local SQLite

### Interface
- Dark, cyan-accented responsive layout
- Live word count, elapsed timer and section-by-section progress
- Responsive on phone, tablet and desktop
- Remembers your tone, strength and model

---

## Quick start

**1. Install the requirements**

- Python 3.10 or newer
- [Ollama](https://ollama.com), then pull a model:

```bash
ollama pull qwen2.5:7b
```

**2. Set up the project**

```bash
python -m venv .venv
.venv\Scripts\activate        # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env        # macOS/Linux: cp .env.example .env
```

**3. Run it**

```bash
python run.py
```

Open **http://127.0.0.1:5000**. Make sure Ollama is running.

---

## Configuration

Edit `.env`, then restart the server.

| Variable | What it does | Default |
|---|---|---|
| `AI_BASE_URL` | OpenAI-compatible API base URL | `http://127.0.0.1:11434/v1` |
| `AI_API_KEY` | API key (any value works for Ollama) | `ollama` |
| `AI_MODEL` | Default model | `qwen2.5:7b` |
| `AI_MODELS` | Comma-separated list for the Model dropdown | `qwen2.5:7b,qwen2.5:3b` |
| `SECRET_KEY` | Flask secret, change before public use | placeholder |

Groq, OpenRouter and OpenAI also work. Change the three `AI_` values and restart.

---

## Choosing a model

| Model | Speed | Quality | Best for |
|---|---|---|---|
| `qwen2.5:3b` | Faster | Basic | Quick drafts on lower-resource machines |
| `qwen2.5:7b` | Slower | Better | Better instruction following and detail retention |
| Hosted models | Fastest | Best | Machines without a GPU |

On a CPU-only computer the 7B model can take a few minutes for long texts. A GPU or a hosted model is much faster.

---

## Tech stack

![Python](https://img.shields.io/badge/Backend-Python_&_Flask-3776AB?style=flat-square)
![JavaScript](https://img.shields.io/badge/Frontend-Vanilla_JS-F7DF1E?style=flat-square&logoColor=black)
![HTML5](https://img.shields.io/badge/Markup-HTML5-E34F26?style=flat-square)
![CSS3](https://img.shields.io/badge/Style-CSS3-1572B6?style=flat-square)
![SQLite](https://img.shields.io/badge/Database-SQLite-003B57?style=flat-square)
![Ollama](https://img.shields.io/badge/AI-Ollama_/_Qwen2.5-6366F1?style=flat-square)

---

## Project structure

```
run.py                   Entry point
app/
  __init__.py            App factory and config
  routes.py              Pages and REST API
  ai.py                  Model calls, chunking, fact checks, cleanup
  prompt.py              System prompt, tone and strength guides, voice matching
  review.py              Instant stiff-phrase and rhythm review
  meaning.py             Key-term coverage check for rewrites
  db.py                  SQLite access
  templates/index.html   User interface
  static/                CSS, JavaScript, favicon
tests/test_ai.py         Unit tests
```

## API

| Method | Route | Purpose |
|---|---|---|
| GET | `/` | The app |
| POST | `/api/rewrite/stream` | Rewrite with live progress, saved to history |
| POST | `/api/rewrite` | Rewrite in a single response |
| POST | `/api/review` | Flag stiff or generic phrasing (no model needed) |
| POST | `/api/meaning` | Flag original sentences that may be missing from a rewrite |
| GET | `/api/history` | Last 50 rewrites |
| GET, DELETE | `/api/history/<id>` | Fetch or delete one rewrite |
| DELETE | `/api/history` | Clear history |
| GET | `/api/export/<id>.txt` | Download a rewrite |

---

## Tests

```bash
python -m unittest discover tests
```

---

## Good to know

- Output quality depends on the model. Larger models keep meaning better, especially at Strong.
- Always review the highlighted result. The checks confirm facts are present, not that every nuance survived.
- No rewriter can guarantee a text will pass an AI detector.
- Flask's development server is meant for personal use. Add authentication and a production server before exposing it publicly.

---

<div align="center">

**Humanly** &nbsp;|&nbsp; Thoughtful edits. Original meaning.

</div>
