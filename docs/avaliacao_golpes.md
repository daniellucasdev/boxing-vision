# Tipo de golpe — automático × revisão

Gerado por `src/avaliar_golpes.py`. Não editar à mão: rodar o script de novo.

1016 golpes detectados dentro dos rounds, 2 lutas (luta_id 92, 94); 0 revisados.

Tipos: jab (reto da mão da frente), direto (reto da mão de trás), cruzado (hook) e gancho (uppercut) da mão da frente ou de trás. A base MHdS não registra tipo de golpe: o gabarito é a revisão feita na página /golpes.

## 1. Distribuição automática (sem revisão)

Golpes detectados dentro dos 3 rounds, por atleta. Percentual de cada tipo atribuído pelas regras.

| luta_id | Atleta | Golpes | Jab | Direto | Cruzado frente | Cruzado trás | Gancho frente | Gancho trás | Sem tipo |
|---|---|---|---|---|---|---|---|---|---|
| 92 | J Edwards | 253 | 8% | 4% | 4% | 5% | 3% | 1% | 75% |
| 92 | S Arzola | 280 | 9% | 5% | 2% | 5% | 1% | 1% | 76% |
| 94 | Keno Marley | 240 | 14% | 6% | 2% | 3% | 2% | 2% | 71% |
| 94 | La Cruz | 243 | 9% | 2% | 2% | 5% | 1% | 0% | 81% |

Sanidade esperada no boxe olímpico: jab e direto como golpes mais frequentes. Muito "sem tipo" indica pose insuficiente (close, oclusão, golpe na direção da câmera) ou guarda indefinida.

## 2. Contra a revisão

Nenhum golpe revisado ainda. Abra a página **Golpes** da interface web (`python src/webapp.py` → /golpes) e revise pelo menos 1 round inteiro de cada luta (~7 min por round). Depois rode este script de novo.
