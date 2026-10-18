"""Fase 0 — Pipeline base: YOLO-pose + tracking em vídeo de boxe.

Desenha o esqueleto de cada pessoa no frame e mantém IDs consistentes
(persist=True + ByteTrack) para separar os 2 boxeadores ao longo do vídeo.

Uso:
    python src/run_pose.py --source video.mp4 --save
    python src/run_pose.py --source 0            # webcam
    python src/run_pose.py --source bus.jpg      # imagem única (smoke test)
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from ultralytics import YOLO

MODEL_DEFAULT = "yolo11n-pose.pt"
REPORT_EVERY = 30  # frames


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pose estimation de boxe (YOLO-pose)")
    parser.add_argument("--source", required=True, help="vídeo, imagem ou índice da webcam")
    parser.add_argument("--model", default=MODEL_DEFAULT, help="pesos yolo*-pose.pt")
    parser.add_argument("--save", action="store_true", help="salva saída anotada em outputs/")
    parser.add_argument("--conf", type=float, default=0.35, help="confiança mínima")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    Path("outputs").mkdir(exist_ok=True)

    model = YOLO(args.model)
    frame_count = 0
    ids_seen: Counter[int] = Counter()

    results = model.track(
        source=args.source,
        conf=args.conf,
        persist=True,  # mantém IDs entre frames
        tracker="bytetrack.yaml",
        stream=True,
        show=not args.save,  # janela ao vivo quando não está salvando
        save=args.save,
        project="outputs",
        name="pose",
        exist_ok=True,
        verbose=False,
    )

    save_dir = None
    for result in results:
        frame_count += 1
        save_dir = getattr(result, "save_dir", save_dir)
        boxes = result.boxes
        if boxes is not None and boxes.id is not None:
            for track_id in boxes.id.int().tolist():
                ids_seen[int(track_id)] += 1

        if frame_count % REPORT_EVERY == 0:
            people = 0 if boxes is None else len(boxes)
            print(f"frame {frame_count:5d} | pessoas no frame: {people} | IDs vistos: {dict(ids_seen)}")

    print("\n=== Resumo ===")
    print(f"frames processados: {frame_count}")
    print(f"pessoas distintas trackeadas: {len(ids_seen)} (IDs: {dict(ids_seen)})")
    if args.save and save_dir:
        print(f"vídeo anotado salvo em {save_dir}")


if __name__ == "__main__":
    main()
