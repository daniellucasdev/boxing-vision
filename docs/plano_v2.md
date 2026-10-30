# Plano v2.0 — da planilha manual ao perfil automático do lutador

## 0. Resumo

- **v1.0 (manual):** um juiz assiste à luta 8× mais devagar, cronometra cada estado do atleta e
  preenche a planilha *Análises MHdS* (1 linha = 1 atleta × 1 round).
- **v2.0 (este software):** o software produz **a mesma planilha automaticamente** a partir do
  vídeo, com três mudanças:
  1. **clinch passa a contar como pausa** → 4 estados: deslocamento, ataque, defesa, pausa;
  2. o deslocamento ganha **direção** (esquerda/direita, frente/trás);
  3. com essas medidas, o software monta um **perfil de estilo por lutador** (explosivo, volume,
     pressão, móvel…) comparado com a base de referência.
- A base manual da v1.0 (786 rounds 2023–2024) vira **ground truth e referência de pace**.

---

## 1. Contrato de saída (o que o software precisa entregar)

Unidade: **1 atleta × 1 round** (mesma da planilha). Estados mutuamente exclusivos; a soma dos
tempos ≈ duração do round (~180 s).

| Estado v2.0 | `t_` (segundos) | `n_` (contagem) | Equivalência com a base v1.0 |
|---|---|---|---|
| Deslocamento | tempo andando pelo ringue **sem atacar**, procurando abertura | nº de trechos contínuos de deslocamento (cada vez que volta a se deslocar após atacar, defender ou pausar) | igual |
| Ataque | tempo em ação ofensiva | nº de ações ofensivas = **golpes + fintas** | igual |
| Defesa | tempo defendendo, **incluindo guarda fechada** | nº de ações defensivas = **bloqueios + esquivas + guarda** | igual |
| **Pausa** | luta parada **+ clinch** | nº de pausas + clinches | `t_clinch + t_pausa`, `n_clinch + n_pausa` |

Na base 2023–2024, a pausa v2.0 fica em média **29,3 s** por round (14,4 s de clinch + 14,9 s de
pausa) e **8,9** ocorrências (5,1 + 3,8).

**Colunas novas da v2.0** (sem equivalente na base — exigem anotação própria, ver §3-C):

| Coluna | Significado |
|---|---|
| `n_golpes`, `n_fintas` | detalhamento do ataque (`n_ataque` = soma) |
| `n_bloqueios`, `n_esquivas`, `n_guarda` | detalhamento da defesa (`n_defesa` = soma) |
| `t_desl_esq`, `t_desl_dir` | tempo em deslocamento lateral para a esquerda/direita **do atleta** |
| `t_desl_frente`, `t_desl_tras` | tempo avançando / recuando em relação ao oponente |
| `n_desl_esq`, `n_desl_dir`, `n_desl_frente`, `n_desl_tras` | contagens correspondentes |
| `dist_percorrida` | distância percorrida no round (em larguras de ombro ou metros, se houver calibração do ringue) |

**Regra de prioridade** quando dois estados acontecem juntos: `Pausa > Ataque > Defesa >
Deslocamento`. **Confirmado com a v1.0:** atacar enquanto se desloca conta como **ataque**. O
deslocamento é o estado residual (tudo que não é ataque, defesa ou pausa), o que bate com a base:
ele ocupa ~106 s dos 180 s.

---

## 2. Definições da v1.0

### Resolvidas

- **Deslocamento** = momentos em que o lutador não está atacando, apenas andando pelo ringue
  enquanto procura uma abertura. *(confirmado por quem fez a v1.0)*
- **Atacar enquanto se desloca = ataque.** *(confirmado)*
- **1 deslocamento = 1 trecho contínuo de deslocamento**, delimitado pelas outras ações. *(inferido
  e verificado na base)* Se isso vale, nenhum round pode ter mais deslocamentos do que a soma das
  outras ações + 1. Isso se confirma nos **786 de 786 rounds**. A conta implica ~23 sequências de
  ataque por round, com ~3 golpes cada, o que é plausível para boxe olímpico.
- **Relógio = tempo de luta do round, não o do vídeo.** *(verificado na base)* 779 dos 786 rounds
  somam entre 175 e 185 s (soma real dos 5 tempos — a coluna "Total" da planilha foi digitada e
  às vezes não bate com a soma), ou seja, repetições da TV não entraram na cronometragem. Os 7
  restantes (170,6 a 201,9 s) são os já apontados como erro de cronometragem → tratar como
  outliers. Para o software, isso significa: **detectar e descartar as repetições da
  transmissão**. *(E3: no Pan 2023 elas só aparecem nos intervalos, então marcar início e fim do
  round já resolve.)*
- **Ataque = golpes + fintas.** A finta é registrada como finta, dentro do ataque. *(confirmado)*
- **Defesa = bloqueios + esquivas + guarda fechada.** Ficar de guarda fechada sob ataque conta
  como defesa. *(confirmado)*
- **Esquerda/direita do ponto de vista do atleta**, não da câmera. *(confirmado)*

### A medir

- **Variação entre anotações:** na mesma luta, a pausa difere entre os atletas — ex.: Edwards
  15,89 s × Lenzi 12,70 s no R1 de Edwards × Lenzi (Olimpíadas 2024). Se a pausa é comum aos
  dois, essa diferença é ruído de anotação, e ela define o **teto de precisão** que o software
  pode alcançar.

---

## 3. Datasets

> **Não existe dataset público que rotule deslocamento lateral de boxeadores.** O deslocamento
> é **medido por geometria** (tracking + compensação de câmera), não aprendido de exemplos. O
> que precisamos é de **ground truth para validar** a medida — por isso o dataset C (próprio) é o
> item mais importante deste plano.
>
> O mesmo vale para **fintas**: nenhum dataset público as rotula. Golpe × finta só pode ser
> aprendido e validado com a anotação C.

| | Dataset | Para que serve aqui | Conteúdo | Situação |
|---|---|---|---|---|
| **A** | **Base MHdS** (própria, v1.0) | Validar e calibrar os agregados por round; referência de pace; estudo de perfis | 786 rounds (~132 lutas, Olimpíadas 2024 + Pan 2023) com tempo + contagem; 248 rounds de 2020 só com tempo | Em `~/Downloads/Análises MHdS 2026-atual.xlsx`; falta converter em CSV |
| **B** | **Vídeos completos das lutas da base** | Rodar o software nas mesmas lutas anotadas e comparar linha a linha | Rounds inteiros, sem cortes de highlight | **Falta reunir.** O `data/olympic.mp4` (Edwards × Lenzi) é um highlight de 170 s e não serve para validação por round |
| **C** | **Anotação temporal própria** (nova) | Ground truth por frame: 4 estados, **direção do deslocamento**, golpe × **finta**, bloqueio × esquiva × guarda. Treino do modelo temporal | A rotina da v1.0 reinstrumentada: a cada tecla, grava-se um timestamp (ver Etapa 1) | A criar — **contribuição da dissertação** |
| **D** | **BoxMAC** (arXiv 2412.18204) | Defesa: seus rótulos batem com as subcategorias da v2.0 (slip/duck → esquiva, block → bloqueio, guard → guarda) e clinch (→ pausa) | 13 rótulos por frame: 6 golpes + stance, slip, block, guard, duck, clinching, no action. >60 mil frames, 15 boxeadores profissionais, 4 câmeras PTZ | Disponibilidade pública **não confirmada** → contatar os autores |
| **E** | **BoxingVI** (arXiv 2511.16524) | Pré-treino da detecção de ataque e, no futuro, do tipo de golpe | 6.915 clipes, 6 golpes (jab, cross, lead/rear hook, lead/rear uppercut), pose 2D já extraída; sparring do YouTube | Público |
| **F** | **Olympic Boxing Punch Classification** (Stefański et al.) | Domínio olímpico real; desfecho do golpe para métricas futuras | 2.278 clipes em 8 classes: cabeça / corpo / bloqueado / errou × mão esquerda/direita; câmera estática | Uso **acadêmico, não comercial** |
| **G** | **SportsMOT** (opcional) | Benchmark de tracking esportivo para avaliar o rastreador | Atletas rápidos e de aparência parecida (basquete, vôlei, futebol) | Público; só se a identidade por cor (Etapa 3) não bastar |

**Esforço estimado do dataset C:** a 8× mais devagar, 1 round de 3 min leva ~24 min por atleta.
15 lutas × 3 rounds × 2 atletas = 90 atleta-rounds ≈ **36 h de anotação**. Mais 2–3 rounds
anotados por uma segunda pessoa para medir a concordância entre anotadores.

---

## 4. Arquitetura v2.0

```
Vídeo da luta
  │  usuário marca: início/fim de cada round, metadados (atleta, cor, categoria, fase…)
  ▼
1. Cortes e replays ──── troca de plano detectada → replay fica fora do tempo do round [E3: cortes]
2. Pose (YOLO-pose) ──── esqueleto de cada pessoa no frame              [já existe]
3. Identidade por cor ── colete AZUL / VERMELHO no tronco → liga direto à coluna `cor`;
                         juiz (camisa clara) e plateia são descartados  [E3 ✅, substitui A/B]
4. Compensação de câmera ─ similaridade entre frames pelo fundo (pessoas mascaradas)
                           → posição dos pés estabilizada; escorço pelos cantos do ringue [E4 ✅]
5. Features por atleta ── velocidade e direção dos pés/quadril, eixo até o oponente,
                          velocidade do punho [já existe], distância entre atletas, contato
6. Classificador de estado ─ etapa A: regras calibradas na base A
                             etapa B: modelo temporal (TCN/LSTM) treinado em C (+ D, E)
7. Agregação ──────────── planilha v2.0 (mesmo layout da base) + eventos com timestamp
8. Perfil ─────────────── métricas de estilo + percentis vs base + relatório (Claude)
```

### Como medir esquerda/direita

- **Eixo do confronto:** vetor do atleta até o oponente, no plano do chão (ponto médio dos
  tornozelos).
- **Frente/trás** = componente do deslocamento ao longo desse eixo; **lateral** = componente
  perpendicular. O sinal (esquerda/direita) é tomado **do ponto de vista do atleta olhando o
  oponente**: assim "circular para a esquerda" significa a mesma coisa para os dois atletas e
  independe do lado da câmera.
- **Guarda:** pelo pé da frente, inferir ortodoxo/canhoto e reportar também "para o lado da mão
  da frente / da mão de trás". Essa é a leitura tática: circular para fora da mão forte do
  adversário.
- **Câmera que acompanha (pan):** a distância entre os atletas não depende do pan, então a
  medida frente/trás é robusta. Já o lateral precisa da compensação da etapa 4; sem ela, um pan
  vira falso deslocamento dos dois atletas.
- **Limitação a declarar:** em vídeo 2D, movimento em direção à câmera aparece encurtado. A
  calibração pelo piso do ringue reduz esse efeito, mas não o elimina com uma câmera só.

---

## 5. Perfil do lutador

Cada métrica é calculada por round e comparada com a base (percentil dentro de **sexo +
categoria**, opcionalmente por round).

| Dimensão | Métricas | Fonte |
|---|---|---|
| **Pace** | golpes/min, % do tempo em cada estado | base A + software |
| **Explosividade** | golpes/s em ataque (base: 1,14–3,28); pico de velocidade do punho; arrancadas (picos de aceleração do quadril); duração e nº de golpes por sequência; razão trabalho:descanso | software |
| **Mobilidade** | distância percorrida; % lateral × frontal; preferência esquerda/direita (e mão da frente/trás) | software (novo) |
| **Pressão** | avanço × recuo; distância média ao oponente | software (novo) |
| **Engano** | fintas / ações de ataque (quem constrói o ataque com fintas × quem só solta golpes) | software (novo) |
| **Defesa** | ações defensivas por golpe recebido; preferência bloqueio × esquiva × guarda | base A + software (detalhamento novo) |
| **Fadiga** | queda R1 → R3 (na base, ~7% menos golpes no 3º round) | base A + software |

**Estilos (rótulos interpretáveis, regras sobre percentis)** — ponto de partida para discutir com
o orientador:

- **Explosivo:** ataques curtos e muito densos (golpes/s alto), pico de velocidade alto, intervalos
  longos entre ataques.
- **Volume:** muitos golpes/min, sequências longas.
- **Pressão:** predomina o avanço e a distância curta.
- **Móvel / de fora:** muito tempo em deslocamento, alto % lateral, recua.
- **Contragolpeador:** alta fração de ataques iniciados logo após uma defesa.

Numa segunda fase, os estilos podem ser **descobertos** por agrupamento (GMM/k-means) sobre a
base, em vez de definidos à mão. Isso já pode ser feito hoje, só com a base A (ver Etapa 2).

---

## 6. Onde entra a IA generativa (Claude) — e onde não entra

**Entra:**
- **Relatório de perfil em PT-BR:** o Claude recebe o JSON de métricas + percentis já calculados e
  escreve a leitura de estilo para o técnico (pontos fortes, padrões, comparação com a categoria).
- **Preparação contra adversário:** comparar os perfis de dois lutadores.
- **Limpeza da base:** sugerir a unificação de grafias (Ghidiff/Ghadfa, Khiznyak/Khyzhniak,
  Uzbequistão/Ubezquistão), sempre com revisão humana.

**Não entra na medição.** Estados, tempos e contagens são calculados de forma determinística e
reprodutível, que é o que a dissertação precisa defender. O Claude só interpreta números
prontos e não pode criar métricas.

**Configuração:** `ANTHROPIC_API_KEY` e `CLAUDE_MODEL` (padrão `claude-opus-5-5`) no `.env`.
⚠️ O SDK `anthropic` 1.x exige **Python ≥ 3.10**; o `.venv` atual é Python 3.9.6 (o do sistema
macOS) → instalar Python 3.12 e recriar o venv na Etapa 0.

---

## 7. Validação (capítulo de resultados)

| Nível | Comparação | Métrica |
|---|---|---|
| Round | software × base A, em lutas **não usadas na calibração** (separar por luta, não por round, para evitar vazamento) | erro médio absoluto (s) por estado e por contagem; Bland-Altman; ICC |
| Frame | software × anotação C | F1 por estado |
| Direção | software × anotação C | acurácia da direção por episódio de deslocamento |
| Teto humano | anotador 1 × anotador 2 nos mesmos rounds | mesma métrica: o software é "bom" se fica dentro dessa variação |
| Perfil | mesmo atleta em lutas diferentes | estabilidade do estilo (ex.: J. Edwards aparece no Pan 2023 e nas Olimpíadas 2024) |

---

## 8. Etapas

O caminho crítico é **E0 → E1 → E3 → E5**. A E2 corre em paralelo desde o início.

| Etapa | O quê | Pronto quando |
|---|---|---|
| **E0 — Preparação** | ✅ *Script reproduzível xlsx → CSV (`src/base_mhds.py`, 786 rounds).* Script reproduzível xlsx → CSV com a limpeza já descrita (duplicatas, grafias, rounds fora de 180 s) e a coluna de pausa v2.0; Python 3.12 + novo venv; reunir os vídeos completos de 10–15 lutas da base; fechar as questões abertas do §2 | CSVs gerados por script; vídeos em `data/lutas/` |
| **E1 — Modo juiz (anotação)** | ✅ *Ferramenta pronta (`/juiz`); falta o critério de pronto.* Na interface web: vídeo a 0,125×, teclas para os 4 estados, golpe, finta, bloqueio, esquiva, guarda e direção (← →); exporta intervalos com timestamp **e** a linha agregada no layout da planilha | Anotar 1 round e reproduzir a linha da base dentro da variação humana |
| **E2 — Estudo da base** (paralelo) | Pace por sexo/categoria/round; efeito de juntar clinch à pausa; primeiros agrupamentos de estilo; vencedor × perdedor | Capítulo descritivo com figuras |
| **E3 — Identidade e tempo** | ✅ *Identidade por cor (`src/identidade.py`, `features.py` v4) e detector de cortes prontos; rounds marcados no modo juiz; repetições automáticas ficam para depois (só aparecem nos intervalos).* Cor azul/vermelho, marcação de rounds, detecção de cortes/replays | Cobertura por atleta e trocas de identidade medidas em vídeos da base B |
| **E4 — Deslocamento** | ✅ *Pronta (`src/deslocamento.py`); conferida a olho, falta comparar com o modo juiz (P6–P8). Mede só com os pés no quadro (19–28% do round no Pan 2023) → proporções.* Compensação de câmera + decomposição frente/trás/lateral | Acurácia da direção × anotação C |
| **E5 — Estados por regras** | ✅ *Pronta (`src/estados.py`): gera pré-anotação no formato do modo juiz. Nas 2 lutas do Pan 2023 da base, médias batem e o erro por linha fica abaixo de chutar a média em desl., defesa e pausa (pausa ±15 s, defesa ±6 s); n_ataque pior (contador, P1).* 4 estados calibrados na base A → planilha v2.0 automática | Erro por estado × base A em lutas de teste |
| **E6 — Modelo temporal** | TCN/LSTM sobre pose para ataque/defesa e suas subcategorias: golpe × finta (C + E), bloqueio × esquiva × guarda (C + D) | Supera as regras da E5 na anotação C |
| **E7 — Perfil + relatório** | Métricas da §5, percentis, relatório pelo Claude, tela de perfil na web | Perfil gerado para todos os atletas da base B |
| **E8 — Futuro** | Tipo de golpe (E), golpe que acerta/erra (F), on-device (ESP32-S3) | — |

**O que já existe e é reaproveitado:** pose + tracking (Fase 0), contador de golpes por regras
(Fase 1 → vira a base de `n_ataque`), gating contra juiz/plateia (que a identidade por cor
substitui com mais robustez) e a interface web (que recebe o modo juiz e a tela de perfil).

---

## Referências

- BoxMAC — https://arxiv.org/abs/2412.18204
- BoxingVI — https://arxiv.org/abs/2511.16524
- Stefański et al., *Boxing Punch Detection with Single Static Camera*, Entropy 2024 —
  https://doaj.org/article/95fc84c03185481199c08b8aa53726b2
- Olympic Boxing Punch Classification (versão Hugging Face) —
  https://huggingface.co/datasets/NealBeans/BoxingDataset
- SportsMOT — https://github.com/MCG-NJU/SportsMOT
- ACM40960/Boxing (código de referência: YOLO11-pose + LSTM para golpes e bloqueios) —
  https://github.com/ACM40960/Boxing
