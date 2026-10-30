# Fontes dos vídeos

Vídeos usados no desenvolvimento e na validação. Ficam em `data/lutas/`, **fora do git**, e são
usados só para pesquisa acadêmica: não são redistribuídos. Baixados com `yt-dlp` no formato 18
(H.264 360p, arquivo único).

```bash
.venv/bin/yt-dlp --extractor-args "youtube:player_client=android" -f 18 \
  -o "data/lutas/<nome>.mp4" "<url>"
```

| Arquivo | Luta | Fonte | Na base MHdS? | Baixado em |
|---|---|---|---|---|
| `pan2023_final_92kg_lacruz_x_keno.mp4` | Julio César La Cruz (CUB, vermelho) × Keno Marley Machado (BRA, azul) — final Pan 2023 | [YouTube — Taylor O'Higgins](https://www.youtube.com/watch?v=wgjC2AgAdjs) (gravação da transmissão Panam Sports, 14:55) | Sim — `luta_id` 94 ("Keno Marley × La Cruz", Final) | 2026-10-29 |
| `pan2023_semi_92mais_edwards_x_arzola.mp4` | Joshua Edwards (USA, azul) × Fernando Arzola (CUB, vermelho) — semifinal Pan 2023 | [YouTube — Coach Malone](https://www.youtube.com/watch?v=zkKh8YdM6DE) (gravação da transmissão Panam Sports, 16:28) | Sim — `luta_id` 92 ("S Arzola × J Edwards", Semifinal) | 2026-10-29 |
| `tokyo2020_final_75kg_oficial.mp4` | Oleksandr Khyzhniak (UKR, vermelho) × Hebert Sousa (BRA, azul) — final 75 kg, Tóquio 2020 | [YouTube — Olympic Games (canal oficial)](https://www.youtube.com/watch?v=8NBCegWPABY) (28:49, inclui repetições e cerimônia) | Não — usado para testar identidade, cortes e repetições | 2026-10-29 |
| `../olympic.mp4` | Joshua Edwards × Diego Lenzi — oitavas, Paris 2024 (highlight) | YouTube — Glamtera Visuals (highlight de 2:50) | Sim (`luta_id` 31), mas é **resumo com cortes**: serve para golpes, não para tempos de round | antes de 2026-10-18 |

## Candidatos ainda não baixados

- [Panam Sports — "BOXEO | Finales Santiago 2023"](https://www.youtube.com/watch?v=XJLyzU8NciU)
  (canal oficial, 1:05:37). Falta conferir quais finais da base ele contém inteiras.
- Canal Taylor O'Higgins: muitas lutas amadoras completas (Pan 2023, qualificatórios 2024),
  com a transmissão original.

## Observações sobre as transmissões

- **Dentro do round não há repetições**: a transmissão só alterna câmeras ao vivo. Repetições,
  closes do corner, torcida e placar aparecem no intervalo entre rounds e depois da luta
  (verificado no round 1 de La Cruz × Keno). Por isso, marcar início e fim do round basta para o
  relógio, e um corte de câmera dentro do round não é tempo perdido.
- O gráfico no canto inferior esquerdo (Pan 2023) mostra o cronômetro oficial do round. No
  futuro, lê-lo pode marcar início e fim automaticamente.
- O ringue do Pan 2023 é azul e a comissão técnica de Cuba veste vermelho; a arquibancada de
  Tóquio é vermelha. A identidade por cor (E3) mede a cor só no corpo do atleta por isso.
