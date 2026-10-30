"""Fase 1 + E3 — features de pose + contador de golpes por regras (v4: identidade por cor).

Histórico: o ByteTrack churna IDs em luta olímpica (225 IDs para 2 boxeadores), então a
v2/v3 abandonou a identidade do tracker e manteve 2 slots espaciais (A/B) casados por
proximidade + gates de distância/escala. Mesmo assim o slot "virava" juiz ou plateia.

v4 (E3): os slots são os cantos — VERMELHO e AZUL — e a cor do uniforme medida nas
regiões do corpo (identidade.py) decide quem é quem:
  - com candidatos das duas cores, vence o par vermelho×azul mais próximo entre si
    (+ continuidade): a comissão técnica de vermelho fica no corner, longe do adversário;
  - sem cor visível (clinch, oclusão), o slot segue pela posição por até MEMORIA_COR
    quadros, nunca aceitando uma detecção da cor do outro canto;
  - corte de câmera (histograma) zera posição/escala/velocidade dos slots — sem
    "golpes" de teleporte e sem gate de escala do plano anterior.

E4: deslocamento de cada canto descontado o movimento da câmera, decomposto em
frente/trás (eixo até o oponente) e esquerda/direita do atleta (deslocamento.py).

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
import os
from collections import deque
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

from deslocamento import (CompensadorCamera, Trajeto, escala_corpo, pes_estimados, ponto_chao,
                          resumir as resumir_deslocamento)
from identidade import DetectorCortes, mascaras_cor, medir_cor

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
MEMORIA_COR = 15    # quadros que um slot segue pela posição sem confirmar a cor (~0,5 s)
ALTURA_COR_MIN = 0.5   # pessoa colorida com caixa < 50% da mais alta = plateia/comissão cortada
MAX_POSICAO_SW = 2.5   # sem cor: distância máx. à última posição (× ombros) em ~0,5 s
ALTURA_POSICAO = (0.6, 1.6)  # sem cor: a caixa precisa ter altura parecida com a última
CORES = ("Vermelho", "Azul")


class Slot:
    """Estado contínuo de um boxeador (canto Vermelho ou Azul), independente do ID do tracker."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.center: np.ndarray | None = None   # centroide da última detecção
        self.sw: float | None = None            # escala esperada (EMA da largura de ombros)
        self.frames = 0                          # frames com detecção
        self.hidden = 0                          # frames sem detecção (diagnóstico)
        self.por_cor = 0                         # frames casados pela cor do uniforme
        self.por_posicao = 0                     # frames casados só pela posição (sem cor)
        self.ultima_cor = -10_000                # último frame com a cor confirmada
        self.altura: float | None = None         # altura da caixa na última detecção
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
        self.sw = sw if self.sw is None else 0.9 * self.sw + 0.1 * sw
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


def _gate_posicao(s: Slot, d: dict) -> bool:
    """Sem cor visível: só aceita quem está quase no mesmo lugar e com o mesmo tamanho."""
    if s.center is None or s.altura is None:
        return False  # sem cor e sem posição conhecida: não há como saber quem é
    if not ALTURA_POSICAO[0] <= d["altura"] / s.altura <= ALTURA_POSICAO[1]:
        return False
    return float(np.linalg.norm(d["centro"] - s.center)) <= MAX_POSICAO_SW * (s.sw or d["sw"] or 1.0)


def casar_por_cor(slots: list[Slot], dets: list[dict], frame_idx: int) -> list[tuple[int | None, str]]:
    """Associa os slots Vermelho/Azul às detecções do quadro.

    dets: [{"centro", "sw", "altura", "cor"}]. Retorna, por slot, (índice da detecção ou
    None, modo), com modo "cor", "posicao" ou "oculto".
    """
    # altura da caixa (não a largura dos ombros, que some no clinch): torcedor e comissão
    # aparecem cortados da cintura para cima; o atleta, de corpo inteiro
    maior = max((d["altura"] for d in dets if d["cor"]), default=0.0)
    cand = {c: [i for i, d in enumerate(dets)
                if d["cor"] == c and d["altura"] >= ALTURA_COR_MIN * maior] for c in CORES}

    def continuidade(s: Slot, i: int) -> float:
        if s.center is None:
            return 0.0
        return float(np.linalg.norm(dets[i]["centro"] - s.center)) / (s.sw or dets[i]["sw"] or 1.0)

    escolha: list[int | None] = [None, None]
    if cand["Vermelho"] and cand["Azul"]:
        def custo(par: tuple[int, int]) -> float:
            r, b = par
            escala = ((dets[r]["sw"] or 1.0) + (dets[b]["sw"] or 1.0)) / 2
            juntos = float(np.linalg.norm(dets[r]["centro"] - dets[b]["centro"])) / escala
            return juntos + continuidade(slots[0], r) + continuidade(slots[1], b)
        escolha = list(min(((r, b) for r in cand["Vermelho"] for b in cand["Azul"]), key=custo))
    else:
        for k, s in enumerate(slots):
            if not cand[s.name]:
                continue
            if s.center is None:   # perdido: a pessoa dessa cor mais em primeiro plano
                escolha[k] = max(cand[s.name], key=lambda i: dets[i]["altura"])
            else:
                escolha[k] = min(cand[s.name], key=lambda i: continuidade(s, i))
    modos = ["cor" if i is not None else "oculto" for i in escolha]

    # sem cor visível: segue pela posição por pouco tempo, nunca com a cor do outro canto
    for k, s in enumerate(slots):
        if escolha[k] is not None or frame_idx - s.ultima_cor > MEMORIA_COR:
            continue
        outra = CORES[1 - k]
        livres = [i for i, d in enumerate(dets)
                  if i not in escolha and d["cor"] != outra and _gate_posicao(s, d)]
        if livres:
            escolha[k] = min(livres, key=lambda i: continuidade(s, i))
            modos[k] = "posicao"
    return list(zip(escolha, modos))


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
    slots = [Slot(c) for c in CORES]
    cortes = DetectorCortes()
    frames_cortes: list[int] = []
    camera = CompensadorCamera()
    trajetos = [Trajeto(fps) for _ in CORES]
    desl: list[dict] = []
    # E5: por quadro, pés (reais ou estimados) e altura do corpo de cada canto + pés do árbitro
    formas = {"pes": (2, 2), "altura": (2,), "arbitro": (2,), "caixa": (2, 4)}
    serie = {k: [] for k in formas}
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
        for chave, forma in formas.items():
            serie[chave].append(np.full(forma, np.nan))
        hsv = cv2.cvtColor(r.orig_img, cv2.COLOR_BGR2HSV)
        corte, _ = cortes.atualizar(hsv)
        if corte:
            frames_cortes.append(frame_idx)
            for s in slots:  # plano novo: posição e escala do anterior não valem mais
                s.reset_match()
                s.sw = None
            camera.reset()
        caixas = r.boxes.xyxy.cpu().numpy() if r.boxes is not None else np.zeros((0, 4))
        M = camera.atualizar(r.orig_img, caixas)
        for t in trajetos:  # sem movimento da câmera conhecido, o histórico não vale mais
            if M is not None:
                t.transportar(M)
            else:
                t.reset()
        if r.keypoints is None or r.boxes is None:
            for s in slots:
                s.reset_match()
            if progress_cb:
                progress_cb(frame_idx, total_frames, 0)
            continue

        kps_all = r.keypoints.data.cpu().numpy()  # (n, 17, 3)
        mascaras = mascaras_cor(hsv)
        dets = []
        for k, caixa in zip(kps_all, caixas):
            ls, rs = k[L_SHOULDER], k[R_SHOULDER]
            if ls[2] > MIN_CONF_KPS and rs[2] > MIN_CONF_KPS:
                centro, sw = (ls[:2] + rs[:2]) / 2, float(np.linalg.norm(ls[:2] - rs[:2]))
            else:
                centro, sw = k[NOSE][:2], None
            dets.append({"centro": centro, "sw": sw, "altura": float(caixa[3] - caixa[1]),
                         "cor": medir_cor(hsv, k, mascaras)["cor"]})
        casamento = casar_por_cor(slots, dets, frame_idx)
        matched = [i for i, _ in casamento]

        for si, (s, (det_i, modo)) in enumerate(zip(slots, casamento)):
            if det_i is None:
                s.hidden += 1
                s.reset_match()
                continue
            if modo == "cor":
                s.por_cor += 1
                s.ultima_cor = frame_idx
            else:
                s.por_posicao += 1
            s.altura = dets[det_i]["altura"]
            # nose do oponente (só quando os 2 slots casados neste frame)
            opp_i = matched[1 - si]
            opp_nose = kps_all[opp_i][NOSE] if opp_i is not None else None
            s.update(frame_idx, kps_all[det_i], opp_nose, rows, collect_rows=save)

        alt_q = r.orig_img.shape[0]
        for si, i in enumerate(matched):
            pe, escala = (pes_estimados(kps_all[i], alt_q), escala_corpo(kps_all[i], caixas[i])) \
                if i is not None else (None, None)
            if pe is not None and escala is not None:
                serie["pes"][-1][si], serie["altura"][-1][si] = pe[0], escala
            if i is not None:
                serie["caixa"][-1][si] = caixas[i]
        if None not in matched:  # árbitro: pessoa sem cor, de corpo inteiro, mais perto dos dois
            meio = (dets[matched[0]]["centro"] + dets[matched[1]]["centro"]) / 2
            maior = max(dets[i]["altura"] for i in matched)
            livres = [i for i, d in enumerate(dets)
                      if i not in matched and d["cor"] is None and d["altura"] >= 0.5 * maior]
            if livres:
                j = min(livres, key=lambda i: float(np.linalg.norm(dets[i]["centro"] - meio)))
                pe = pes_estimados(kps_all[j], alt_q)
                if pe is not None:
                    serie["arbitro"][-1] = pe[0]
        pes = [ponto_chao(kps_all[i], alt_q) if i is not None else None for i in matched]
        for si, (t, pe) in enumerate(zip(trajetos, pes)):
            escala = escala_corpo(kps_all[matched[si]], caixas[matched[si]]) if pe is not None else None
            if escala is not None:
                t.adicionar(frame_idx, pe[0], pe[1], escala)
        for si, t in enumerate(trajetos):
            oi = matched[1 - si]
            opp = pes_estimados(kps_all[oi], alt_q) if oi is not None else None
            v = t.velocidade(frame_idx)
            if v is None or pes[si] is None or opp is None:
                continue
            sep = (opp[0] - pes[si][0]) / t.altura   # só a direção entra na decomposição
            desl.append({"frame": frame_idx, "slot": CORES[si],
                         "vx": round(float(v[0]), 3), "vy": round(float(v[1]), 3),
                         "ex": round(float(sep[0]), 3), "ey": round(float(sep[1]), 3),
                         "fonte": pes[si][1], "fonte_opp": opp[1]})

        if save:
            annotated = r.plot()
            for s, det_i in zip(slots, matched):
                if det_i is None:
                    continue
                x1, y1 = (int(v) for v in r.boxes.xyxy[det_i][:2])
                label = f"[{s.name}] golpes L{s.punches['L']}/R{s.punches['R']}"
                cor_bgr = (60, 60, 255) if s.name == "Vermelho" else (255, 170, 40)
                cv2.putText(annotated, label, (x1, max(20, y1 - 8)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, cor_bgr, 2)
            if writer is None:
                h, w = annotated.shape[:2]
                for fourcc in ("avc1", "mp4v"):
                    writer = cv2.VideoWriter(
                        str(out_dir / "annotated.partial.mp4"),
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
        # publica atomicamente: mp4 so e reproduzivel com o arquivo fechado
        partial = out_dir / "annotated.partial.mp4"
        if partial.exists():
            os.replace(partial, out_dir / "annotated.mp4")

    minutes = frame_idx / fps / 60
    deslocamento = resumir_deslocamento(desl, fps, frame_idx)
    total = sum(s.punches["L"] + s.punches["R"] for s in slots)
    payload = {
        "video": str(source),
        "frames": frame_idx,
        "fps": fps,
        "duracao_s": round(frame_idx / fps, 1) if fps else 0,
        "versao": "v5-desl",
        "total": total,
        "por_minuto": round(total / minutes, 1) if minutes > 0 else 0.0,
        "params": {
            "refractory": REFRACTORY, "k_sigma": K_SIGMA, "min_speed": MIN_SPEED,
            "min_ext": MIN_EXT, "window": WINDOW, "peak_confirm": True,
            "max_speed": MAX_SPEED, "max_ext": MAX_EXT,
            "memoria_cor": MEMORIA_COR, "altura_cor_min": ALTURA_COR_MIN,
            "max_posicao_sw": MAX_POSICAO_SW,
        },
        "slots": [
            {"slot": s.name, "frames": s.frames,
             "cobertura_pct": round(100 * s.frames / max(frame_idx, 1)),
             "hidden": s.hidden,
             "por_cor_pct": round(100 * s.por_cor / max(frame_idx, 1)),
             "por_posicao_pct": round(100 * s.por_posicao / max(frame_idx, 1)),
             "golpes_L": s.punches["L"], "golpes_R": s.punches["R"],
             "golpes_total": s.punches["L"] + s.punches["R"]}
            for s in slots
        ],
        "eventos": sorted([e for s in slots for e in s.events], key=lambda e: e["frame"]),
        "cortes": frames_cortes,
        "deslocamento": deslocamento,
    }

    if save:
        with open(out_dir / "features.csv", "w", newline="") as f:
            if rows:
                wcsv = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                wcsv.writeheader()
                wcsv.writerows(rows)
        np.savez_compressed(out_dir / "serie.npz", fps=fps,
                            **{k: np.array(v).reshape(len(v), *formas[k])
                               for k, v in serie.items()})
        with open(out_dir / "deslocamento.csv", "w", newline="") as f:
            if desl:
                wcsv = csv.DictWriter(f, fieldnames=list(desl[0].keys()))
                wcsv.writeheader()
                wcsv.writerows(desl)
        with open(out_dir / "eventos.json", "w") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    return payload


def main() -> None:
    ap = argparse.ArgumentParser(description="v4: identidade por cor + contador de golpes por regras")
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

    print("\n=== Resumo (v4, identidade por cor) ===")
    print(f"frames: {payload['frames']} | fps: {payload['fps']:.1f} | duracao: {payload['duracao_s']}s")
    for s in payload["slots"]:
        print(f"{s['slot']}: cobertura {s['cobertura_pct']}% (cor {s['por_cor_pct']}% · "
              f"posição {s['por_posicao_pct']}%) | golpes L {s['golpes_L']} / R {s['golpes_R']} "
              f"= {s['golpes_total']}")
    print(f"cortes de câmera: {len(payload['cortes'])}")
    d = payload["deslocamento"]
    print(f"\ndeslocamento (escorço {d['escorco']}):")
    for slot, a in d["atletas"].items():
        print(f"  {slot}: medido {a['medido_pct']}% | " + " · ".join(
            f"{k} {a['t_' + k]}s/{a['n_' + k]}x" for k in ("frente", "tras", "esq", "dir"))
            + f" | parado {a['t_parado']}s | {a['distancia_corpos']} corpos")
    print(f"\nTOTAL: {payload['total']} golpes ({payload['por_minuto']}/min)")
    if args.save:
        print("saídas em outputs/ (features.csv, eventos.json, annotated.mp4)")


if __name__ == "__main__":
    main()
