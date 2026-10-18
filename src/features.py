"""Fase 1 — extração de features de pose + contador de golpes por regras (v2).

Por que v2: o ByteTrack churna IDs em luta olímpica (225 IDs distintos para
2 boxeadores, oclusões com juiz/câmeras no frame). Janelas por ID nunca
enchem e o contador zera. A v2 abandona a identidade do tracker e mantém
2 SLOTS espaciais (boxeador A/B): a cada frame, as detecções são casadas
ao slot mais próximo (centroide); slot oculto apenas carrega estado.

Detector por slot (sem ML, baseline):
  - velocidade do punho normalizada pela largura dos ombros (invariante a escala)
  - golpe = pico LOCAL de velocidade (v[t-1] <= v[t] > v[t+1]) acima de
    média + K_SIGMA*desvio da janela deslizante, com braço estendido
    (ext >= MIN_EXT) e refratário por braço (combos não contam 2x)

CLI:
  python src/features.py --source data/olympic.mp4 --save

Programático (usado pela interface web):
  from features import run_pipeline
  payload = run_pipeline("video.mp4", out_dir=Path("outputs/jobs/x"),
                         progress_cb=fn)
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import deque
from itertools import permutations
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

# Keypoints COCO-17 (padrão do ultralytics pose)
NOSE = 0
L_SHOULDER, R_SHOULDER = 5, 6
L_WRIST, R_WRIST = 9, 10

REFRACTORY = 12   # frames entre golpes do mesmo braço
K_SIGMA = 3.0     # limiar = média + K_SIGMA*desvio da janela
MIN_SPEED = 0.35  # piso absoluto (px/frame normalizado pela largura dos ombros)
MIN_EXT = 1.05    # braço precisa estar estendido (punho longe do ombro)
WINDOW = 45       # janela deslizante para estatística de velocidade
MIN_CONF_KPS = 0.3
MIN_HIST = 8      # amostras mínimas antes de detectar
MAX_SPEED = 10.0  # acima disso = corte de câmera/teleporte (ombros/frame), reseta janela
MAX_EXT = 3.0     # braço não tem 3 larguras de ombro; acima = keypoint quebrado


class Slot:
    """Estado contínuo de um boxeador (slot A ou B), independente do ID do tracker."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.center: np.ndarray | None = None   # centroide da última detecção
        self.frames = 0                          # frames com detecção
        self.prev: dict[str, np.ndarray | None] = {"L": None, "R": None}
        self.hist: dict[str, deque[float]] = {"L": deque(maxlen=WINDOW), "R": deque(maxlen=WINDOW)}
        self.last_punch: dict[str, int] = {"L": -10_000, "R": -10_000}
        self.punches = {"L": 0, "R": 0}
        self.events: list[dict] = []

    def reset_match(self) -> None:
        """Frame sem detecção: punho some (próxima medida vira amostra neutra)."""
        self.center = None
        self.prev["L"] = None
        self.prev["R"] = None

    def update(
        self,
        frame_idx: int,
        kps: np.ndarray,
        opp_nose: np.ndarray | None,
        rows: list[dict],
        collect_rows: bool,
    ) -> None:
        self.frames += 1
        ls, rs = kps[L_SHOULDER], kps[R_SHOULDER]
        if ls[2] < MIN_CONF_KPS or rs[2] < MIN_CONF_KPS:
            return
        sw = float(np.linalg.norm(ls[:2] - rs[:2]))
        if sw < 1.0:
            return
        self.center = ((ls[:2] + rs[:2]) / 2 + kps[NOSE][:2]) / 2

        feats: dict[str, object] = {}
        for arm, w_i, s_i in (("L", L_WRIST, L_SHOULDER), ("R", R_WRIST, R_SHOULDER)):
            w = kps[w_i]
            if w[2] < MIN_CONF_KPS:
                self.prev[arm] = None
                continue

            speed = 0.0
            if self.prev[arm] is not None:
                speed = float(np.linalg.norm(w[:2] - self.prev[arm][:2])) / sw
            if speed > MAX_SPEED:
                # corte de câmera / troca brutal: descontinuidade, não é movimento
                self.hist[arm].clear()
                self.prev[arm] = None
                continue
            self.prev[arm] = w.copy()
            self.hist[arm].append(speed)

            ext = float(np.linalg.norm(w[:2] - kps[s_i][:2])) / sw
            if ext > MAX_EXT:
                continue  # keypoint quebrado neste frame: sem evento, sem feature
            head_dist: float | None = None
            if opp_nose is not None and opp_nose[2] > MIN_CONF_KPS:
                head_dist = float(np.linalg.norm(w[:2] - opp_nose[:2])) / sw

            h = self.hist[arm]
            thresh = max(float(np.mean(h)) + K_SIGMA * float(np.std(h)), MIN_SPEED)
            # pico local: a medida do MEIO (t-1) confirma quando chega a de t
            is_punch = False
            peak_speed = 0.0
            if len(h) >= MIN_HIST + 1:
                v_prev, v_peak, v_next = h[-3], h[-2], h[-1]
                is_punch = (
                    v_peak >= v_prev
                    and v_peak > v_next
                    and v_peak >= thresh
                    and ext >= MIN_EXT
                    and (frame_idx - self.last_punch[arm]) > REFRACTORY
                )
                peak_speed = v_peak
            if is_punch:
                self.punches[arm] += 1
                self.last_punch[arm] = frame_idx - 1
                self.events.append({
                    "frame": frame_idx - 1,
                    "boxer": self.name,
                    "braco": arm,
                    "vel": round(peak_speed, 3),
                    "ext": round(ext, 3),
                    "dist_cabeca_opp": round(head_dist, 3) if head_dist is not None else None,
                })

            if collect_rows:
                feats[f"vel_{arm}"] = round(speed, 3)
                feats[f"ext_{arm}"] = round(ext, 3)
                feats[f"dist_cabeca_opp_{arm}"] = (
                    round(head_dist, 3) if head_dist is not None else ""
                )
                feats[f"limiar_{arm}"] = round(thresh, 3)

        if collect_rows and feats:
            rows.append({"frame": frame_idx, "slot": self.name, "ombros_px": round(sw, 1), **feats})


def match_slots(slots: list[Slot], dets: list[np.ndarray]) -> list[int | None]:
    """Cada slot ao centroide mais próximo (2 slots, n detecções → atribuição de custo mínimo).

    Retorna índice da detecção por slot (None = slot oculto neste frame).
    """
    n = len(dets)
    assign: list[int | None] = [None, None]
    if n == 0:
        return assign
    if slots[0].center is None or slots[1].center is None:
        # inicialização (ou perda total): primeiras n detecções em ordem
        for i, s in enumerate(slots):
            if s.center is None and i < n:
                assign[i] = i
        return assign
    if n == 1:
        d = [float(np.linalg.norm(dets[0] - s.center)) for s in slots]
        assign[int(np.argmin(d))] = 0
        return assign
    best, best_cost = assign, float("inf")
    for i, j in permutations(range(n), 2):
        cost = float(np.linalg.norm(dets[i] - slots[0].center)) + float(
            np.linalg.norm(dets[j] - slots[1].center))
        if cost < best_cost:
            best_cost, best = cost, [i, j]
    return best


def run_pipeline(
    source: str,
    *,
    model_path: str = "yolo11n-pose.pt",
    conf: float = 0.35,
    out_dir: Path | None = None,
    save: bool = True,
    max_frames: int = 0,
    progress_cb=None,
) -> dict:
    """Roda o pipeline completo e devolve o payload de resultados.

    progress_cb(frame_idx, total_frames, total_punches) é chamado a cada frame
    processado (para a barra de progresso da interface web).
    """
    out_dir = Path(out_dir) if out_dir else Path("outputs")
    if save:
        out_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(source)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    cap.release()

    model = YOLO(model_path)
    slots = [Slot("A"), Slot("B")]
    rows: list[dict] = []
    frame_idx = 0
    writer = None

    results = model.track(
        source=source,
        conf=conf,
        persist=True,
        tracker="bytetrack.yaml",
        stream=True,
        verbose=False,
    )

    for r in results:
        frame_idx += 1
        if max_frames and frame_idx > max_frames:
            break
        if r.keypoints is None or r.boxes is None:
            for s in slots:
                s.reset_match()
            if progress_cb:
                progress_cb(frame_idx, total_frames, 0)
            continue

        kps_all = r.keypoints.data.cpu().numpy()  # (n, 17, 3)
        centers = [
            (k[L_SHOULDER][:2] + k[R_SHOULDER][:2]) / 2
            if k[L_SHOULDER][2] > MIN_CONF_KPS and k[R_SHOULDER][2] > MIN_CONF_KPS
            else k[NOSE][:2]
            for k in kps_all
        ]
        matched = match_slots(slots, centers)

        for si, (s, det_i) in enumerate(zip(slots, matched)):
            if det_i is None:
                s.reset_match()
                continue
            # nose do oponente (só quando os 2 slots casados neste frame)
            opp_i = matched[1 - si]
            opp_nose = kps_all[opp_i][NOSE] if opp_i is not None else None
            s.update(frame_idx, kps_all[det_i], opp_nose, rows, collect_rows=save)

        if save:
            annotated = r.plot()
            for s, det_i in zip(slots, matched):
                if det_i is None:
                    continue
                x1, y1 = (int(v) for v in r.boxes.xyxy[det_i][:2])
                label = f"[{s.name}] golpes L{s.punches['L']}/R{s.punches['R']}"
                cv2.putText(annotated, label, (x1, max(20, y1 - 8)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            if writer is None:
                h, w = annotated.shape[:2]
                for fourcc in ("avc1", "mp4v"):
                    writer = cv2.VideoWriter(
                        str(out_dir / "annotated.mp4"),
                        cv2.VideoWriter_fourcc(*fourcc), fps, (w, h)
                    )
                    if writer.isOpened():
                        break
            writer.write(annotated)

        if progress_cb:
            tot = sum(s.punches["L"] + s.punches["R"] for s in slots)
            progress_cb(frame_idx, total_frames, tot)

    if writer is not None:
        writer.release()

    minutes = frame_idx / fps / 60
    total = sum(s.punches["L"] + s.punches["R"] for s in slots)
    payload = {
        "video": str(source),
        "frames": frame_idx,
        "fps": fps,
        "duracao_s": round(frame_idx / fps, 1) if fps else 0,
        "versao": "v2-slots",
        "total": total,
        "por_minuto": round(total / minutes, 1) if minutes > 0 else 0.0,
        "params": {
            "refractory": REFRACTORY, "k_sigma": K_SIGMA, "min_speed": MIN_SPEED,
            "min_ext": MIN_EXT, "window": WINDOW, "peak_confirm": True,
            "max_speed": MAX_SPEED, "max_ext": MAX_EXT,
        },
        "slots": [
            {"slot": s.name, "frames": s.frames,
             "cobertura_pct": round(100 * s.frames / max(frame_idx, 1)),
             "golpes_L": s.punches["L"], "golpes_R": s.punches["R"],
             "golpes_total": s.punches["L"] + s.punches["R"]}
            for s in slots
        ],
        "eventos": [e for s in slots for e in s.events],
    }

    if save:
        with open(out_dir / "features.csv", "w", newline="") as f:
            if rows:
                wcsv = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                wcsv.writeheader()
                wcsv.writerows(rows)
        with open(out_dir / "eventos.json", "w") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    return payload


def main() -> None:
    ap = argparse.ArgumentParser(description="Fase 1 v2: slots espaciais + contador por regras")
    ap.add_argument("--source", required=True, help="vídeo de entrada")
    ap.add_argument("--model", default="yolo11n-pose.pt")
    ap.add_argument("--conf", type=float, default=0.35)
    ap.add_argument("--save", action="store_true", help="grava features.csv, eventos.json e annotated.mp4")
    ap.add_argument("--max-frames", type=int, default=0, help="processa só os N primeiros frames (0 = tudo)")
    args = ap.parse_args()

    def cb(idx: int, total: int, punches: int) -> None:
        if total:
            print(f"\rframe {idx}/{total} | golpes: {punches}", end="", flush=True)
        else:
            print(f"\rframe {idx} | golpes: {punches}", end="", flush=True)

    payload = run_pipeline(
        args.source, model_path=args.model, conf=args.conf,
        save=args.save, max_frames=args.max_frames,
        progress_cb=cb if args.save else None,
    )

    print("\n\n=== Resumo (v2, slots espaciais) ===")
    print(f"frames: {payload['frames']} | fps: {payload['fps']:.1f} | duracao: {payload['duracao_s']}s")
    for s in payload["slots"]:
        print(f"slot {s['slot']}: cobertura {s['cobertura_pct']}% | "
              f"golpes L {s['golpes_L']} / R {s['golpes_R']} = {s['golpes_total']}")
    print(f"\nTOTAL: {payload['total']} golpes ({payload['por_minuto']}/min)")
    if args.save:
        print("saídas em outputs/ (features.csv, eventos.json, annotated.mp4)")


if __name__ == "__main__":
    main()
