# Boxing Vision 🥊

Visão computacional + IA para boxe olímpico: contar **golpes** (jab, cross, hook, uppercut), **bloqueios** e **esquivas** a partir de vídeo.

## Arquitetura alvo

```
Vídeo → YOLO Pose (keypoints por frame, por boxeador)
      → Tracking (separar os 2 atletas no ringue)
      → Classificador temporal (LSTM/TCN sobre sequências de pose)
      → Eventos: golpe / bloqueio / esquiva → contadores por atleta
```

**Decisão central:** YOLO de detecção pura não resolve — golpe é uma *ação* (sequência temporal).
YOLO **Pose** extrai o esqueleto; a camada temporal classifica a ação e o contador vira
detecção de eventos (picos de probabilidade + refratário para não contar feint/combo 2x).

## Roadmap

- [ ] **Fase 0 — fundação (andando sem treinar nada):** YOLO-pose rodando em vídeo de sparring, esqueleto desenhado, 2 boxeadores separados por tracking
- [ ] **Fase 1 — features de pose:** velocidade do punho, distância punho→cabeça do oponente, ângulo de cotovelo; baseline com regras antes de qualquer ML
- [ ] **Fase 2 — classificador temporal:** LSTM/TCN sobre janelas de ~25 frames de keypoints (dataset BoxingVI p/ golpes; anotação própria p/ bloqueios e esquivas)
- [ ] **Fase 3 — contagem:** detecção de eventos + refratário; relatório por round
- [ ] **Fase 4 (futuro):** YOLO nano quantizado on-device (ESP32-S3)

## Datasets

| Dataset | Conteúdo | Link |
|---|---|---|
| **BoxingVI** (arxiv 2511.16524) | 6.915 clipes de golpes, 6 tipos, com timestamps + pose keypoints | https://arxiv.org/abs/2511.16524 |
| serp-ai/boxing-punch-recognition-dataset | punches classificados | https://github.com/serp-ai/boxing-punch-recognition-dataset |
| piotr-stefanski/boxing-fight-video-analysis | classificação de golpes de boxe **olímpico** | https://github.com/piotr-stefanski/boxing-fight-video-analysis |
| ACM40960/Boxing (referência de código) | YOLO11-pose + LSTM: punches e blocks | https://github.com/ACM40960/Boxing |

> Bloqueios e esquivas têm pouquíssimos dados públicos — a anotação dessa parte será própria
> (gravar sparring controlado e rotular sequências).

## Como rodar

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# vídeo de exemplo (ou webcam: --source 0)
python src/run_pose.py --source caminho/do/video.mp4 --save
# saída anotada fica em runs/pose/outputs/pose (padrão do ultralytics)
```

## Estrutura

```
boxing-vision/
├── src/
│   └── run_pose.py      # Fase 0: pose + tracking em vídeo
├── data/                # vídeos e datasets (gitignored)
├── models/              # pesos (gitignored)
├── outputs/             # vídeos anotados (gitignored)
└── docs/                # decisões e anotações
```
