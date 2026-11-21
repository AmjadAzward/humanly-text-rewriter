import csv
import io
from flask import Blueprint, render_template, request, jsonify, Response
import json
from .ai import rewrite_text, rewrite_iter, available_models, AIConfigurationError, AIRequestError
from .db import get_db
from .review import review_text

main = Blueprint("main", __name__)

TONES = ["Natural", "Professional", "Friendly", "Casual", "Academic", "Persuasive", "Concise"]
STRENGTHS = ["Polish", "Light", "Medium", "Strong"]

@main.get("/")
def index():
    return render_template("index.html", tones=TONES, strengths=STRENGTHS, models=available_models())

@main.post("/api/review")
def api_review():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "")[:30000]
    return jsonify(findings=review_text(text))


def _line(obj):
    return json.dumps(obj) + chr(10)


def _pick_model(data):
    model = (data.get("model") or "").strip()
    return model if model in available_models() else None


@main.post("/api/rewrite/stream")
def api_rewrite_stream():
    data = request.get_json(silent=True) or {}
    original = (data.get("text") or "").strip()
    tone = data.get("tone", "Natural")
    strength = data.get("strength", "Medium")
    previous = (data.get("previous_text") or "").strip()
    if not original or len(original) > 30000 or tone not in TONES or strength not in STRENGTHS:
        return jsonify(error="Enter valid text (up to 30,000 characters), tone and strength."), 400
    model = _pick_model(data)
    voice = (data.get("voice_sample") or "").strip()

    def generate():
        parts, warnings = [], []
        try:
            for number, total, chunk, note in rewrite_iter(original, tone, strength, previous, model, voice):
                parts.append(chunk)
                if note:
                    warnings.append(f"Section {number}: {note}.")
                yield _line({"type": "progress", "done": number, "total": total})
            rewritten = "".join(parts).strip()
            with get_db() as conn:
                cursor = conn.execute(
                    "INSERT INTO rewrites (original_text, rewritten_text, tone, strength, previous_text) VALUES (?, ?, ?, ?, ?)",
                    (original, rewritten, tone, strength, previous))
                conn.commit()
                rewrite_id = cursor.lastrowid
            yield _line({"type": "done", "id": rewrite_id, "rewritten_text": rewritten, "warnings": warnings})
        except (AIConfigurationError, AIRequestError) as exc:
            yield _line({"type": "error", "error": str(exc)})

    return Response(generate(), mimetype="application/x-ndjson", headers={"X-Accel-Buffering": "no"})


@main.post("/api/rewrite")
def api_rewrite():
    data = request.get_json(silent=True) or {}
    original = (data.get("text") or "").strip()
    tone = data.get("tone", "Natural")
    strength = data.get("strength", "Medium")
    previous = (data.get("previous_text") or "").strip()

    if not original:
        return jsonify(error="Enter some text to rewrite."), 400
    if len(original) > 30000:
        return jsonify(error="Please keep the text under 30,000 characters."), 400
    if tone not in TONES or strength not in STRENGTHS:
        return jsonify(error="Choose a valid tone and rewrite strength."), 400
    try:
        rewritten, warnings = rewrite_text(original, tone, strength, previous, _pick_model(data),
                                          (data.get("voice_sample") or "").strip())
        with get_db() as conn:
            cursor = conn.execute(
                """INSERT INTO rewrites
                (original_text, rewritten_text, tone, strength, previous_text)
                VALUES (?, ?, ?, ?, ?)""",
                (original, rewritten, tone, strength, previous)
            )
            conn.commit()
            rewrite_id = cursor.lastrowid
        return jsonify(id=rewrite_id, rewritten_text=rewritten, warnings=warnings)
    except AIConfigurationError as exc:
        return jsonify(error=str(exc), setup_required=True), 503
    except AIRequestError as exc:
        return jsonify(error=str(exc)), 502

@main.get("/api/history")
def history():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, original_text, rewritten_text, tone, strength, created_at FROM rewrites ORDER BY id DESC LIMIT 50"
        ).fetchall()
    return jsonify(items=[dict(row) for row in rows])

@main.get("/api/history/<int:rewrite_id>")
def history_item(rewrite_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM rewrites WHERE id = ?", (rewrite_id,)).fetchone()
    if row is None:
        return jsonify(error="Rewrite not found."), 404
    return jsonify(item=dict(row))

@main.delete("/api/history/<int:rewrite_id>")
def delete_history(rewrite_id):
    with get_db() as conn:
        conn.execute("DELETE FROM rewrites WHERE id = ?", (rewrite_id,))
        conn.commit()
    return jsonify(success=True)

@main.delete("/api/history")
def clear_history():
    with get_db() as conn:
        conn.execute("DELETE FROM rewrites")
        conn.commit()
    return jsonify(success=True)

@main.get("/api/export/<int:rewrite_id>.txt")
def export_text(rewrite_id):
    with get_db() as conn:
        row = conn.execute("SELECT rewritten_text FROM rewrites WHERE id = ?", (rewrite_id,)).fetchone()
    if row is None:
        return jsonify(error="Rewrite not found."), 404
    return Response(row["rewritten_text"], mimetype="text/plain",
                    headers={"Content-Disposition": f"attachment; filename=rewrite-{rewrite_id}.txt"})
