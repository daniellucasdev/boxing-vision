"""Interface web do Boxing Vision.

Páginas:
  /       Início — luta pré-analisada (outputs/eventos.json + annotated.mp4), anotações em
          andamento, vídeos disponíveis e análise sob demanda de clipes (job em background
          com barra de progresso).
  /juiz   Modo juiz (E1) — anotação temporal de 1 atleta × 1 round, a 0,125× como na v1.0;
          gera a linha da planilha v2.0 e compara com a base MHdS (data/referencia/).

Rodar:
  source .venv/bin/activate
  python src/webapp.py            # http://127.0.0.1:5000
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path

import cv2
from flask import Flask, Response, abort, jsonify, request, render_template, send_from_directory
from werkzeug.exceptions import HTTPException
from werkzeug.utils import secure_filename

import anotacao
from base_mhds import carregar_base, sem_acento

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "outputs"
JOBS = OUT / "jobs"
UPLOADS = JOBS / "uploads"
DATA = REPO / "data"
LUTAS = DATA / "lutas"          # vídeos de lutas completas (upload do modo juiz)
ANOTACOES = DATA / "anotacoes"  # 1 JSON por anotação (atleta × round)
VIDEO_EXT = (".mp4", ".mov", ".m4v", ".webm")
MAX_UPLOAD_MB = 2048            # luta completa em boa resolução passa de 300 MB
ID_RE = re.compile(r"[0-9a-f]{32}")

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
    payload["eventos"] = sorted(payload.get("eventos", []), key=lambda e: e.get("frame", 0))
    vid = OUT / "annotated.mp4"
    payload["video_url"] = None
    payload["video_em_processamento"] = False
    if vid.exists():
        cap = cv2.VideoCapture(str(vid))
        ok = cap.isOpened() and cap.get(cv2.CAP_PROP_FRAME_COUNT) > 0
        cap.release()
        if ok:
            payload["video_url"] = "/media/annotated.mp4"
        else:
            payload["video_em_processamento"] = True  # job reescrevendo o arquivo
    payload["titulo"] = Path(payload.get("video", "?")).name
    # fundo do destaque: o vídeo original (sem caixas/esqueletos) se estiver em data/
    original = DATA / payload["titulo"]
    payload["video_original_url"] = (
        f"/media/data/{payload['titulo']}" if original.is_file() and _toca_no_navegador(original) else None)
    return payload


@app.errorhandler(HTTPException)
def _erro_http(exc: HTTPException):
    if request.path.startswith("/api/"):
        return jsonify(error=exc.description), exc.code
    return exc


def _codec(path: Path) -> str:
    cap = cv2.VideoCapture(str(path))
    cc = int(cap.get(cv2.CAP_PROP_FOURCC))
    cap.release()
    return "".join(chr((cc >> 8 * i) & 0xFF) for i in range(4)).strip().lower()


def _toca_no_navegador(path: Path) -> bool:
    return _codec(path) not in ("fmp4", "mp4v", "xvid", "divx")


def _listar_videos() -> list[dict]:
    """Vídeos em data/ e data/lutas/. MPEG-4 Part 2 (FMP4/mp4v) não toca em navegador."""
    videos = []
    for pasta in (LUTAS, DATA):
        if not pasta.exists():
            continue
        for p in sorted(pasta.iterdir()):
            if p.suffix.lower() in VIDEO_EXT and p.is_file():
                rel = p.relative_to(DATA).as_posix()
                videos.append({
                    "nome": rel, "url": f"/media/data/{rel}",
                    "mb": round(p.stat().st_size / 1e6, 1), "codec": _codec(p),
                    "toca_no_navegador": _toca_no_navegador(p),
                })
    return videos


def _caminho_anotacao(aid: str) -> Path:
    if not ID_RE.fullmatch(aid):
        abort(400, "id inválido")
    return ANOTACOES / f"{aid}.json"


def _ler_anotacao(aid: str) -> dict:
    p = _caminho_anotacao(aid)
    if not p.exists():
        abort(404, "anotação não encontrada")
    return json.loads(p.read_text(encoding="utf-8"))


def _gravar_anotacao(doc: dict) -> None:
    ANOTACOES.mkdir(parents=True, exist_ok=True)
    p = _caminho_anotacao(doc["id"])
    tmp = p.with_suffix(".partial")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)  # atômico: autosave nunca deixa JSON pela metade


def _linha_base(chave: str) -> dict | None:
    if not chave:
        return None
    return next((r for r in carregar_base() if r["chave"] == chave), None)


def _com_resumo(doc: dict) -> dict:
    resumo = anotacao.resumir(doc)
    base = _linha_base(doc["meta"].get("base_chave", ""))
    return {**doc, "resumo": resumo, "base": base, "comparacao": anotacao.comparar(resumo, base)}


def _listar_anotacoes() -> list[dict]:
    if not ANOTACOES.exists():
        return []
    docs = []
    for p in ANOTACOES.glob("*.json"):
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        r = anotacao.resumir(doc)
        docs.append({"id": doc["id"], "meta": doc["meta"], "video": doc["video"],
                     "atualizado_em": doc.get("atualizado_em", ""), "n_marcas": len(doc["marcas"]),
                     "t_total": r["t_total"], "aberto": r["aberto"]})
    return sorted(docs, key=lambda d: d["atualizado_em"], reverse=True)


def _csv(texto: str, nome: str) -> Response:
    # BOM: o Excel abre UTF-8 com acentos corretos
    return Response("﻿" + texto, mimetype="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{nome}"'})


@app.get("/")
def index():
    preset = _load_preset()
    anotacoes = _listar_anotacoes()
    if preset:
        # se alguém já anotou esse vídeo no modo juiz, o destaque ganha o nome da luta
        meta = next((a["meta"] for a in anotacoes
                     if a["video"] == preset["titulo"] and a["meta"].get("oponente")), None)
        if meta:
            preset["luta"] = f"{meta['atleta']} × {meta['oponente']}"
            preset["luta_onde"] = " · ".join(x for x in (meta["competicao"], meta["fase"], meta["categoria"]) if x)
    return render_template("index.html", preset=preset, pagina="inicio",
                           videos=_listar_videos(), anotacoes=anotacoes)


@app.get("/juiz")
def juiz():
    return render_template("juiz.html", pagina="juiz", tem_base=bool(carregar_base()))


@app.get("/api/videos")
def api_videos():
    return jsonify(_listar_videos())


@app.post("/api/videos")
def api_upload_video():
    file = request.files.get("video")
    if file is None or file.filename == "":
        return jsonify(error="envie um arquivo de vídeo (campo 'video')"), 400
    nome = secure_filename(file.filename)
    if not nome.lower().endswith(VIDEO_EXT):
        return jsonify(error="formato não suportado — use mp4/mov/m4v/webm"), 400
    LUTAS.mkdir(parents=True, exist_ok=True)
    destino = LUTAS / nome
    if destino.exists():
        destino = LUTAS / f"{destino.stem}_{uuid.uuid4().hex[:6]}{destino.suffix}"
    file.save(destino)
    return jsonify(next(v for v in _listar_videos() if v["nome"] == destino.relative_to(DATA).as_posix())), 201


@app.get("/media/data/<path:nome>")
def data_video(nome: str):
    if not nome.lower().endswith(VIDEO_EXT):
        abort(404)
    return send_from_directory(DATA, nome)  # bloqueia ../; suporta Range (seek no vídeo)


@app.get("/api/base")
def api_base():
    q = sem_acento(request.args.get("q", "").strip())
    if len(q) < 2:
        return jsonify([])
    achados = [r for r in carregar_base()
               if q in sem_acento(r["atleta"]) or q in sem_acento(r["oponente"])
               or q in sem_acento(r["pais"])]
    return jsonify(achados[:60])


@app.get("/api/anotacoes")
def api_anotacoes():
    return jsonify(_listar_anotacoes())


@app.post("/api/anotacoes")
def api_criar_anotacao():
    try:
        doc = anotacao.validar(request.get_json(force=True, silent=True) or {})
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    video = (DATA / doc["video"]).resolve()
    if (DATA.resolve() not in video.parents or video.suffix.lower() not in VIDEO_EXT
            or not video.is_file()):
        return jsonify(error="vídeo não encontrado em data/"), 400
    agora = datetime.now().isoformat(timespec="seconds")
    doc = {"id": uuid.uuid4().hex, "criado_em": agora, "atualizado_em": agora, **doc}
    _gravar_anotacao(doc)
    return jsonify(_com_resumo(doc)), 201


@app.get("/api/anotacoes/<aid>")
def api_anotacao(aid: str):
    return jsonify(_com_resumo(_ler_anotacao(aid)))


@app.put("/api/anotacoes/<aid>")
def api_salvar_anotacao(aid: str):
    antigo = _ler_anotacao(aid)
    try:
        novo = anotacao.validar(request.get_json(force=True, silent=True) or {})
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    doc = {**antigo, **novo, "video": antigo["video"],
           "atualizado_em": datetime.now().isoformat(timespec="seconds")}
    _gravar_anotacao(doc)
    return jsonify(_com_resumo(doc))


@app.delete("/api/anotacoes/<aid>")
def api_apagar_anotacao(aid: str):
    p = _caminho_anotacao(aid)
    if not p.exists():
        abort(404, "anotação não encontrada")
    p.unlink()
    return "", 204


@app.get("/api/anotacoes/<aid>/<tipo>.csv")
def api_anotacao_csv(aid: str, tipo: str):
    doc = _ler_anotacao(aid)
    base = f"{secure_filename(doc['meta'].get('atleta') or 'atleta')}_R{doc['meta'].get('round') or '?'}"
    if tipo == "linha":
        return _csv(anotacao.csv_linhas([doc]), f"{base}_linha.csv")
    if tipo == "intervalos":
        return _csv(anotacao.csv_intervalos(doc), f"{base}_intervalos.csv")
    if tipo == "acoes":
        return _csv(anotacao.csv_acoes(doc), f"{base}_acoes.csv")
    abort(404)


@app.get("/api/planilha.csv")
def api_planilha():
    """Planilha v2.0 completa: 1 linha por anotação (atleta × round)."""
    docs = [_ler_anotacao(a["id"]) for a in _listar_anotacoes()]
    return _csv(anotacao.csv_linhas(docs), "planilha_v2.csv")


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
