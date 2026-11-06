# E5 — Estados automáticos × base MHdS

Gerado por `src/avaliar_estados.py`. Não editar à mão: rodar o script de novo.

12 linhas (atleta × round) de 2 lutas (luta_id 92, 94).

## Métricas por variável

| Variável | Média auto | Média base | MAE | MAE chutando a média | Viés (auto − base) | ± LoA 95% | ICC(A,1) | r |
|---|---|---|---|---|---|---|---|---|
| t deslocamento | 105,4 | 103,2 | 13,0 | 15,3 | 2,2 | 36,9 | 0,46 | 0,48 |
| t ataque | 32,2 | 31,9 | 5,5 | 5,5 | 0,3 | 14,2 | 0,20 | 0,20 |
| t defesa | 13,8 | 17,8 | 5,8 | 6,8 | -3,9 | 16,5 | 0,05 | 0,08 |
| t pausa | 28,6 | 27,3 | 14,6 | 16,8 | 1,2 | 38,2 | 0,54 | 0,55 |
| n deslocamento | 58,7 | 55,0 | 7,3 | 7,0 | 3,7 | 17,6 | 0,03 | 0,04 |
| n ataque | 73,1 | 61,8 | 14,5 | 13,4 | 11,3 | 27,1 | 0,34 | 0,47 |
| n defesa | 28,9 | 29,8 | 5,8 | 7,9 | -0,8 | 18,4 | 0,34 | 0,38 |
| n pausa | 10,2 | 7,5 | 5,0 | 4,5 | 2,7 | 10,3 | 0,44 | 0,52 |

Piso humano (docs/estudo_base.md, seção 6): a pausa v2.0 do mesmo round difere em média 5,0 s entre os dois cantos (ICC 0,91). O automático é útil quando o MAE fica perto disso e abaixo do MAE de chutar a média.

Com poucas lutas o ICC e o r são instáveis (cada luta tem só 6 linhas, e as 2 do mesmo round compartilham a pausa). Leia o MAE primeiro.

## Linha a linha (automático / base, segundos)

| luta_id | Round | Canto | Atleta | Deslocamento | Ataque | Defesa | Pausa |
|---|---|---|---|---|---|---|---|
| 94 | 1 | Vermelho | La Cruz | 102 / 101 | 34 / 19 | 11 / 37 | 34 / 23 |
| 94 | 1 | Azul | Keno Marley | 100 / 101 | 32 / 42 | 14 / 9 | 34 / 28 |
| 94 | 2 | Vermelho | La Cruz | 100 / 106 | 23 / 26 | 14 / 23 | 43 / 24 |
| 94 | 2 | Azul | Keno Marley | 97 / 102 | 31 / 37 | 8 / 9 | 43 / 31 |
| 94 | 3 | Vermelho | La Cruz | 101 / 63 | 36 / 35 | 12 / 17 | 31 / 65 |
| 94 | 3 | Azul | Keno Marley | 108 / 69 | 30 / 31 | 10 / 8 | 31 / 73 |
| 92 | 1 | Vermelho | S Arzola | 116 / 128 | 39 / 40 | 14 / 13 | 10 / 0 |
| 92 | 1 | Azul | J Edwards | 125 / 127 | 26 / 34 | 18 / 19 | 10 / 0 |
| 92 | 2 | Vermelho | S Arzola | 117 / 130 | 38 / 28 | 18 / 17 | 7 / 6 |
| 92 | 2 | Azul | J Edwards | 127 / 114 | 32 / 36 | 14 / 20 | 7 / 11 |
| 92 | 3 | Vermelho | S Arzola | 85 / 106 | 30 / 27 | 18 / 17 | 47 / 31 |
| 92 | 3 | Azul | J Edwards | 86 / 93 | 33 / 27 | 14 / 25 | 47 / 35 |
