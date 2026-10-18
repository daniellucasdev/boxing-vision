# Decisões do projeto

## 2026-10-18 — criação do projeto

- **YOLO Pose + camada temporal** em vez de YOLO de detecção pura: golpe/bloqueio/esquiva são
  ações (sequência de movimento); bounding box não captura isso. Referências com esse desenho:
  ACM40960/Boxing (YOLO11-pose + LSTM) e ECSS (93% F1 contando golpes com pose + TCN/LSTM).
- **Escopo do MVP:** câmera lateral fixa (vídeo próprio ou sparring do YouTube), NÃO broadcast
  de TV — oclusão e câmera distante tornam broadcast ordens de magnitude mais difícil.
  "Olímpico" entra como domínio/técnica, não como fonte de vídeo no início.
- **Baseline com regras antes de ML:** velocidade do punho + distância punho→cabeça do oponente
  já dá um contador razoável; o classificador temporal entra depois para refinar e classificar tipos.
- **Datasets:** BoxingVI (golpes, com pose já extraída) como base pública; bloqueios/esquivas
  serão anotados manualmente (gravação própria).
- **Contador = detecção de eventos** com refratário (~N frames sem novo evento) para não
  contar feints e combinações duas vezes.

## 2026-10-18 — Fase 1

- **Features normalizadas pela largura dos ombros** (invariante a escala/distância da câmera):
  velocidade do punho, extensão (punho→ombro) e distância punho→cabeça do oponente (só com
  exatamente 2 pessoas no frame — elimina juiz/plateia do sinal).
- **Regra de golpe:** pico acima de média + 3σ da janela deslizante (45 frames), braço estendido
  (≥1.05× ombros), piso absoluto de velocidade e refratário de 12 frames por braço.
- **YouTube bloqueou clients web/desktop com SABR** ("page needs to be reloaded"); cliente
  `android` do yt-dlp passou. nightly + `--extractor-args "youtube:player_client=android"`.
- Lição de execução: luta completa (~5100 frames, 170s) passa de 7 min no pipeline — rodar
  com `--save` em background ou cortar trecho antes.

## 2026-10-18 — Fase 1 v2: slots espaciais (achado central)

- **ByteTrack churna em luta olímpica:** 225 IDs distintos para 2 boxeadores no vídeo de 170s
  (highlight com cortes, juiz/filmadores no frame). Top-2 IDs cobriam só **23%** dos frames;
  63% dos IDs morriam em <1s. Janelas por ID nunca enchem → contador da v1 dava 29 golpes
  na luta inteira e **0** num segmento de 40s.
- **Correção: 2 slots espaciais A/B** — abandonar a identidade do tracker e casar detecções ao
  slot mais próximo (atribuição de custo mínimo por centróides dos ombros). Oclusão só esconde
  o slot; as janelas ficam sempre quentes. Cobertura por slot: 80% (vs 23%).
- **Cortes de câmera geram "golpes" falsos** (teleporte de keypoints): vel 27 ombros/frame,
  ext 21. Filtro físico resolve: velocidade >10 ombros/frame reseta a janela (descontinuidade),
  extensão >3 ombros é keypoint quebrado. No segmento de 40s: 34 → 16 eventos, todos plausíveis.
- **Confirmação de pico local** (v[t-1] <= v[t] > v[t+1]) marca o evento no frame do pico,
  não no primeiro frame acima do limiar.
- Resultado do segmento de 40s: 16 golpes (24/min somando os 2 boxeadores), balanceado por
  braço (8/8). Validação humana pendente (assistir o annotated.mp4 e anotar a verdade).

## 2026-10-18 — v3: gating de associação (juiz/plateia não captura mais slot)

- **Relato do usuário:** em vários momentos A ou B "virava" o juiz ou alguém da plateia.
  Causa: a associação por proximidade não tinha limite — slot ocluído agarrava a detecção
  mais próxima, fosse quem fosse, e herdava todo o histórico.
- **Fine-tuning descartado (decisão):** o detector acerta; o defeito é na associação, camada
  acima do modelo. Retreinar pesos não endereça o bug.
- **Correção (gating):** (1) distância máxima de re-captura = 4× a largura de ombros do slot
  (boxeador não teleporta); (2) coerência de escala — a detecção precisa ter largura de ombros
  entre 0.35× e 2.8× a do slot (plateia ao fundo é minúscula, filmador perto é gigante).
  Slot escala esperada via EMA (0.9/0.1). Slot sem candidata viável fica oculto (contado
  como `hidden` e exposto na UI).
- 4 casos sintéticos de gating validados (juiz pequeno/longe, oclusão, gigante em primeiro
  plano, re-captura após perda total).
- **Eventos agora em ordem cronológica** no payload (`eventos.json`) e na UI — antes vinham
  agrupados por slot (todos do A, depois todos do B).



