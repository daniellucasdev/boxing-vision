"""Interface web do Boxing Vision.

Modos de demonstração:
  1. Luta pré-analisada (outputs/eventos.json + outputs/annotated.mp4) — abre instantâneo.
  2. Análise sob demanda: upload de clipe (ou clipe de exemplo) → job em background
     com barra de progresso ao vivo → resultado com vídeo anotado.

Rodar:
  source .venv/bin/activate
  python src/webapp.py            # http://127.0.0.1:5000
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import uuid
from pathlib import Path

from flask import Flask, jsonify, request, render_template, send_from_directory
from werkzeug.utils import secure_filename

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "outputs"
JOBS = OUT / "jobs"
UPLOADS = JOBS / "uploads"
MAX_UPLOAD_MB = 300

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
app.json.ensure_ascii = False


def _load_preset() -> dict | None:
    result = OUT / "eventos.json"
    if not result.exists():
        return None
    try:
        payload = json.loads(result.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    # normaliza schema legado (CLI antigo não gravava total/duracao_s/por_minuto)
    frames = payload.get("frames") or 0
    fps = payload.get("fps") or 25.0
    slots = payload.get("slots", [])
    payload.setdefault("total", sum(s.get("golpes_total", 0) for s in slots))
    payload.setdefault("duracao_s", round(frames / fps, 1) if fps else 0)
    minutes = frames / fps / 60 if fps else 0
    payload.setdefault(
        "por_minuto", round(payload["total"] / minutes, 1) if minutes > 0 else 0.0)
    for s in slots:
        s.setdefault("cobertura_pct", round(100 * s.get("frames", 0) / max(frames, 1)))
        s.setdefault("golpes_total", s.get("golpes_L", 0) + s.get("golpes_R", 0))
    payload["video_url"] = "/media/annotated.mp4" if (OUT / "annotated.mp4").exists() else None
    payload["titulo"] = Path(payload.get("video", "?")).name
    return payload


@app.get("/")
def index():
    return render_template("index.html", preset=_load_preset())


@app.post("/api/analyze")
def analyze():
    demo = request.form.get("demo")
    if demo:
        src = REPO / "data" / secure_filename(demo)
        if not src.exists():
            return jsonify(error="clipe de exemplo não encontrado"), 404
    else:
        file = request.files.get("video")
        if file is None or file.filename == "":
            return jsonify(error="envie um arquivo de vídeo (campo 'video')"), 400
        if not file.filename.lower().endswith((".mp4", ".mov", ".avi", ".mkv", ".webm")):
            return jsonify(error="formato não suportado — use mp4/mov/avi/mkv/webm"), 400
        UPLOADS.mkdir(parents=True, exist_ok=True)
        job_id = uuid.uuid4().hex
        src = UPLOADS / f"{job_id}_{secure_filename(file.filename)}"
        file.save(src)

    job_id = uuid.uuid4().hex
    job_dir = JOBS / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "source.txt").write_text(str(src))

    subprocess.Popen(
        [sys.executable, str(REPO / "src" / "analyze.py"),
         "--source", str(src), "--job-dir", str(job_dir)],
        cwd=str(REPO / "src"),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return jsonify(job_id=job_id), 202


@app.get("/api/job/<job_id>")
def job_status(job_id: str):
    if not re.fullmatch(r"[0-9a-f]{32}", job_id):
        return jsonify(error="id inválido"), 400
    job_dir = JOBS / job_id
    progress = job_dir / "progress.json"
    result = job_dir / "result.json"

    if result.exists():
        try:
            payload = json.loads(result.read_text())
        except json.JSONDecodeError:
            payload = {"status": "error", "message": "resultado corrompido"}
        if payload.get("status") == "done":
            payload["video_url"] = f"/media/jobs/{job_id}/annotated.mp4"
        return jsonify(payload)

    if progress.exists():
        try:
            return jsonify(json.loads(progress.read_text()))
        except json.JSONDecodeError:
            pass
    return jsonify(status="queued", pct=0, punches=0)


@app.get("/media/annotated.mp4")
def preset_video():
    return send_from_directory(OUT, "annotated.mp4")


@app.get("/media/jobs/<job_id>/<path:filename>")
def job_video(job_id: str, filename: str):
    if not re.fullmatch(r"[0-9a-f]{32}", job_id):
        return jsonify(error="id inválido"), 400
    return send_from_directory(JOBS / job_id, filename)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1", help="0.0.0.0 para acessar de outro aparelho na rede")
    ap.add_argument("--port", type=int, default=5000)
    args = ap.parse_args()
    print(f"Boxing Vision web — http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=False, threaded=True)
