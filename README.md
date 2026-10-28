# Frami 2.0 🥊

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

- [x] **Fase 0 — fundação:** YOLO-pose rodando em vídeo de sparring, esqueleto desenhado, 2 boxeadores separados por tracking ✅
- [x] **Fase 1 — features de pose + contador por regras:** velocidade do punho, extensão do braço, distância punho→cabeça do oponente; baseline com pico estatístico (média + Kσ) + refratário antes de qualquer ML ✅ (validado em Edwards vs Lenzi, Olympics 2024)
- [ ] **Fase 2 — classificador temporal:** LSTM/TCN sobre janelas de ~25 frames de keypoints (dataset BoxingVI p/ golpes; anotação própria p/ bloqueios e esquivas)
- [ ] **Fase 3 — contagem refinada:** classificação por tipo (jab/cross/hook/uppercut), bloqueios e esquivas; relatório por round
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

# Fase 0: pose + tracking (vídeo anotado em runs/)
python src/run_pose.py --source data/video.mp4 --save

# Fase 1: features + contador de golpes (outputs/features.csv, eventos.json, annotated.mp4)
python src/features.py --source data/video.mp4 --save
```

### Interface web (demonstração)

```bash
# opção 1: duplo-clique em scripts/start_web.command (Finder)
# opção 2: terminal
source .venv/bin/activate
python src/webapp.py                # http://127.0.0.1:5000
python src/webapp.py --host 0.0.0.0 # acessível de outro aparelho na rede
```

A home mostra a luta pré-analisada (instantâneo) e permite analisar clipes novos
(upload ou clipe de exemplo de 12s) com barra de progresso ao vivo.

## Estrutura

```
boxing-vision/
├── src/
│   ├── run_pose.py      # Fase 0: pose + tracking em vídeo
│   ├── features.py      # Fase 1: features de pose + contador por regras (CLI + run_pipeline)
│   ├── analyze.py       # job de análise p/ web (progress.json + result.json)
│   ├── webapp.py        # interface web Flask
│   └── templates/
│       └── index.html   # página única da interface
├── scripts/
│   └── start_web.command  # inicia a web (duplo-clique no Finder)
├── data/                # vídeos e datasets (gitignored)
├── models/              # pesos (gitignored)
├── outputs/             # vídeos anotados (gitignored)
└── docs/                # decisões e anotações
```
