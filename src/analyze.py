"""Job de análise para a interface web: roda o pipeline e grava progresso/resultado.

Chamado pelo webapp em subprocesso:
  python src/analyze.py --source <video> --job-dir outputs/jobs/<id> [--max-frames N]

Arquivos gravados em --job-dir:
  progress.json — {"status", "pct", "frame", "total", "punches"} (atualizado por frame)
  result.json   — payload completo quando termina (ou status=error + message)
  annotated.mp4, features.csv, eventos.json
"""

from __future__ import annotations

import argparse
import json
import traceback
from pathlib import Path

from features import run_pipeline


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--job-dir", required=True)
    ap.add_argument("--max-frames", type=int, default=0)
    args = ap.parse_args()

    job_dir = Path(args.job_dir)
    job_dir.mkdir(parents=True, exist_ok=True)
    progress_path = job_dir / "progress.json"
    result_path = job_dir / "result.json"

    def cb(idx: int, total: int, punches: int) -> None:
        pct = round(100 * idx / total, 1) if total else 0.0
        progress_path.write_text(json.dumps({
            "status": "running", "pct": pct,
            "frame": idx, "total": total, "punches": punches,
        }))

    try:
        cb(0, args.max_frames or 0, 0)
        payload = run_pipeline(
            args.source,
            out_dir=job_dir,
            save=True,
            max_frames=args.max_frames,
            progress_cb=cb,
        )
        payload["status"] = "done"
        result_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    except Exception as exc:  # noqa: BLE001 — job isolado: erro vira resultado consultável
        result_path.write_text(json.dumps({
            "status": "error",
            "message": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
