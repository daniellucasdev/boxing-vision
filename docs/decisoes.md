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
