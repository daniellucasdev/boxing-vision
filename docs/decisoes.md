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




## 2026-10-29 — v2.0: planilha da v1.0 como contrato de saída

- **Saída = a planilha da v1.0** (juiz assistindo 8× mais devagar): 1 linha por atleta × round,
  tempo (`t_`) e contagem (`n_`) por estado. A base manual (786 rounds 2023–2024) vira ground
  truth e referência de pace. Edwards × Lenzi (o vídeo que já temos) está na base, mas nosso
  arquivo é highlight de 170 s → não serve para validar por round; precisamos dos rounds inteiros.
- **Clinch passa a ser pausa:** 4 estados (deslocamento, ataque, defesa, pausa). Mapeamento da
  base: `t_pausa_v2 = t_clinch + t_pausa`, idem para `n_`.
- **Deslocamento com direção no referencial do atleta** (olhando o oponente), não no da câmera:
  "circular para a esquerda" significa o mesmo para os dois atletas e independe do lado da câmera.
  Frente/trás é robusto a pan da câmera; lateral exige compensação de câmera.
- **Nenhum dataset público rotula deslocamento:** a direção é medida por geometria e validada com
  anotação própria (modo juiz com timestamps), que é também a contribuição de dados da dissertação.
- **Claude só interpreta, não mede:** relatório de perfil a partir das métricas prontas. A medição
  continua determinística e reprodutível. Chave em `.env` (fora do git); SDK 1.x exige
  Python ≥ 3.10 e o venv atual é 3.9.6.
- **Ruído da própria base:** a pausa difere entre os dois atletas da mesma luta (Edwards 15,89 s
  × Lenzi 12,70 s no R1), o que indica variação de anotação. Medir a concordância entre
  anotadores e usá-la como teto de precisão.

## 2026-10-29 — definições da v1.0 confirmadas

- **Deslocamento** = andar pelo ringue sem atacar, procurando abertura (confirmado por quem fez a
  v1.0). **Atacar se deslocando conta como ataque** → prioridade Pausa > Ataque > Defesa >
  Deslocamento.
- **1 deslocamento = 1 trecho contínuo**, delimitado pelas outras ações. Verificado na base: em
  786/786 rounds, `n_desl <= n_atq + n_def + n_clinch + n_pausa + 1`; isso implica ~23
  sequências de ataque/round com ~3 golpes cada.
- **Relógio do round, não do vídeo:** 779/786 rounds somam 175–185 s (soma real dos 5 tempos; a
  coluna "Total" da planilha foi digitada e às vezes diverge — ex. Edwards R1: 180,82 digitado ×
  183,82 somado) → repetições da TV ficaram fora. O software precisa detectar e descartar as
  repetições; os 7 rounds de 170,6 a 201,9 s são os erros de cronometragem já conhecidos.
- **Ataque = golpes + fintas** (finta registrada como finta, dentro do ataque); **defesa =
  bloqueios + esquivas + guarda fechada**. A v2.0 entrega o total (`n_ataque`, `n_defesa`,
  comparável com a base) e o detalhamento por subcategoria. A base da v1.0 só tem os totais.
  Nenhum dataset público rotula fintas → só a anotação própria cobre golpe × finta. Os rótulos
  do BoxMAC batem com as subcategorias de defesa (slip/duck, block, guard).
- **Esquerda/direita no referencial do atleta**, confirmado.

## 2026-10-29 — E0 (base em CSV) e E1 (modo juiz)

- **Base MHdS → CSV por script** (`src/base_mhds.py`, só biblioteca padrão): 786 rounds, 132 lutas,
  todas as categorias com código. `t_total` recalculado como soma dos 5 tempos (a coluna digitada
  diverge às vezes). Planilha copiada para `data/referencia/` (fora do git).
- **Modo juiz = estados por mudança + ações pontuais.** O anotador marca só *quando o estado muda*
  (segmentos contíguos, sem lacunas — a soma fecha por construção) e marca ações no instante em que
  acontecem. Uma ação de ataque/defesa abre o estado correspondente se ele não estiver ativo
  (regra "atacar se deslocando = ataque").
- **Fora (repetição/corte)** é um estado próprio que quebra trechos e não entra em `t_total` —
  reproduz o relógio de luta da v1.0.
- **Resumo calculado só no servidor** (`src/anotacao.py`), a cada autosave: uma única
  implementação das regras de contagem, testável e igual para a tela e os CSVs. O navegador só
  desenha.
- **Avisos de consistência** em vez de bloqueios: round sem fim, total fora de 175–185 s, trecho de
  ataque/defesa sem ação, ação fora do estado. O anotador decide.
- Anotações em `data/anotacoes/` (JSON, escrita atômica) — **fora do git**; precisam de backup.
- Interface redesenhada (estilo Netflix, paleta azul); corrigido de passagem o botão do clipe de
  exemplo, que quebrava a exibição do resultado (`btnDemo` não existia na página).
- `demo12s.mp4` e `segment40s.mp4` são MPEG-4 Part 2 e não tocam no navegador; o modo juiz avisa.

## 2026-10-29 — E3 (identidade por cor + cortes de câmera)

- **Os slots espaciais da v3 trocavam de atleta o tempo todo.** Medido pela cor do colete em cada
  slot, em 3 vídeos: o slot A ficava com a cor "errada" em 40–48% dos quadros com cor definida, e
  o B em 33–48%. Ou seja, metade dos golpes da v3 ia para o atleta errado.
- **v4: o slot É a cor do canto (Vermelho/Azul).** Cada esqueleto recebe uma cor medida só no
  corpo (`src/identidade.py`): metade de cima do tronco encolhida, faixa do calção e círculos das
  luvas. A caixa inteira não serve, porque pega o ringue azul do Pan 2023 e a arquibancada
  vermelha de Tóquio. O tronco precisa confirmar a cor sozinho, senão a luva de látex azul do juiz
  decidia.
- **Filtros contra comissão técnica e plateia:** a caixa candidata precisa ter ≥ 50% da altura
  da maior pessoa colorida do quadro. Sem cor (clinch, costas, borrão), o slot segue a posição
  por no máximo 15 quadros, se a altura for parecida (0,6–1,6×) e estiver a ≤ 2,5 larguras de
  ombro. Nunca aceita alguém com a cor do outro canto.
- **Cortes de câmera:** é corte quando a diferença média de pixels (canal V, 64×36) passa de 0,12,
  ou quando a correlação do histograma HSV cai abaixo de 0,55. Só o histograma não bastava: as
  trocas entre câmeras do mesmo ringue mantêm a correlação entre 0,74 e 0,99. Na final do Pan
  2023, todos os 27 cortes conferidos à mão foram detectados; os falsos positivos são as vinhetas
  de logo e uma panorâmica rápida. No corte, o slot esquece posição e escala.
- **Repetições:** nas transmissões do Pan 2023 não há repetição *dentro* do round; elas só
  aparecem no intervalo, entre vinhetas. Por isso o relógio do round sai de marcar início e fim
  (manual, no modo juiz), e a detecção automática de repetições fica para depois (vinheta → OCR
  do cronômetro na tela).
- **Resultado (inspeção visual de 40 quadros por vídeo, dentro dos rounds):** ~3 erros em 40 na
  final La Cruz × Keno e no highlight Edwards × Lenzi; nenhum erro dentro do round na semi
  Edwards × Arzola. Os erros restantes são pessoas de azul ao fundo em planos abertos. Fora dos
  rounds (apresentação, intervalo), a comissão técnica de vermelho ou azul-marinho ainda recebe
  rótulo, o que não importa porque esse tempo não entra na planilha.
- **Custo da escolha:** ambos os atletas identificados em 58–77% dos quadros (v3: 89–95%). A v3
  "via" mais porque sempre chutava alguém. A v4 prefere deixar o slot vazio a errar o atleta, e
  por isso conta ~15–20% menos golpes.
- Vídeos de teste baixados de fontes confiáveis (transmissões oficiais ou gravações da
  transmissão Panam Sports) → `docs/fontes_videos.md`.

## 2026-10-29 — E4 (deslocamento: câmera + direção)

- **Câmera:** pontos de textura do fundo (pessoas mascaradas pelas caixas do YOLO) seguidos por
  fluxo óptico → similaridade (pan, tilt, zoom) por RANSAC (`src/deslocamento.py`). Os gráficos
  da TV ficam parados na tela mesmo com a câmera andando: um grupo de pontos que se move de forma
  coerente vence os pontos parados, e "câmera parada" exige a maioria dos pontos parados. Sem
  consenso, o quadro fica sem medida (melhor que errado). Testado: movimento sintético conhecido
  com placar fixo, erro < 0,1 px; em 3 vídeos reais o fundo alinhado muda 39–49% menos, e só 3%
  dos quadros pioram.
- **Ponto no chão = meio dos tornozelos; o quadril não serve.** Numa esquiva o quadril sobe e
  desce na tela, e o vertical da tela é profundidade ampliada ~3× (escorço): uma esquiva virava
  "recuou meio corpo". Pés a menos de 3% da borda de baixo também são descartados (pé cortado, o
  YOLO inventa o tornozelo). Para o **eixo** até o oponente basta a direção, então os pés dele
  podem ser estimados pelo quadril (+1,47 tronco, medido nos quadros de corpo inteiro).
- **Escala pelo tronco, não pela caixa:** em plano fechado a caixa é cortada pela borda e o
  atleta "encolhe", inflando a velocidade (mediana pelo quadril saía 2× a dos tornozelos). Altura
  = tronco ÷ 0,285 (mediana medida no Pan 2023). Unidade: corpos/s.
- **Velocidade = inclinação da reta** ajustada aos pontos dos últimos 0,5 s (já descontada a
  câmera), não "último − primeiro"; acima de 2,5 corpos/s (~4,5 m/s) é salto de keypoint.
- **Escorço fixo em 0,33, medido pela geometria do ringue.** Os 4 cantos do ringue (quadrado de
  6,1 m) num plano aberto da câmera principal dão uma homografia: no centro do ringue, 1 m em
  profundidade aparece com 0,33 do tamanho de 1 m na horizontal (0,30–0,38 do fundo para a
  frente), igual nas duas lutas do Pan medidas. A primeira tentativa, estimar por vídeo
  supondo constante a distância entre os atletas, foi descartada: o mínimo era raso demais e o
  valor variava de 0,22 a 1,0 conforme o trecho.
- **Esquerda/direita do atleta:** a câmera fica acima do ringue, então a tela é uma vista de cima
  sem espelho (achatada). A esquerda de quem olha na direção u é u girado 90° no sentido
  anti-horário da tela. Testado com o atleta olhando para a direita, para o fundo e para a câmera.
- **Conferência visual** (folhas com os quadros −15 e +12 alinhados ao quadro 0 pela câmera
  estimada, trilha dos pés na janela e eixo até o oponente): 12 amostras dentro do round, 8
  claramente certas, 1 plausível, 3 duvidosas, todas com pés na borda da tela (agora
  descartados). Um caso sutil confirmou o escorço: andar para a esquerda da tela era ir para a
  *direita* do atleta, porque o oponente estava mais perto da câmera.
- **Sem viés de câmera:** a velocidade média na tela fica perto de zero nos dois vídeos. O Azul
  ir mais para a esquerda (nas duas lutas) aparece igual com o oponente de qualquer lado da tela:
  é do atleta, não da geometria.
- **Cobertura:** a direção só é medida com os pés no quadro, 19–28% do round no Pan 2023 (planos
  fechados não mostram os pés). Por isso o resultado é lido como **proporção do tempo medido**,
  não em segundos absolutos. O estado "deslocamento" da planilha (sem atacar/defender) vem na E5;
  a E4 mede a direção do movimento em qualquer estado.

## 2026-10-30 — E5 (4 estados por regras → pré-anotação do modo juiz)

- **Saída = marcas do modo juiz, não a planilha direto** (`src/estados.py`). O software escreve as
  mesmas trocas de estado e ações que o juiz marcaria; a contagem, os CSVs e a comparação com a
  base são os de `anotacao.py`, e a pré-anotação pode ser aberta e corrigida no modo juiz. A ação
  "defesa" sem subtipo (`n_defesa_sem_tipo`) foi criada porque as regras não separam bloqueio,
  esquiva e guarda.
- **Prioridade da v1.0 por quadro:** Pausa > Ataque > Defesa > Deslocamento.
- **Pausa** (igual para os dois atletas): clinch = pés a menos de 0,45 corpo no chão (escorço da
  E4) por ≥ 0,8 s; em close, sem os pés, caixas sobrepostas em ≥ 45% da menor (limiar tirado dos
  quadros em que as duas medidas existem: mediana 0,44–0,51 no clinch, ~0 com os atletas a mais de
  0,7 corpo); ou árbitro entre os atletas. Testado e descartado: "árbitro perto de um atleta"
  (advertência); ele fica a 0,5–1 corpo de alguém o tempo todo.
- **Ataque:** ±0,25 s em volta de cada golpe detectado; golpes a menos de 0,35 s formam uma
  sequência. Na base são ~0,46 s por ação.
- **Defesa:** golpe do oponente fora do próprio ataque. O limite punho→nariz (1,2 largura de
  ombro) foi abandonado: o detector marca o golpe no pico de velocidade, antes de o punho chegar,
  e a esquiva afasta a cabeça; quase nenhuma defesa sobrava. O limite ficou em 10 larguras (só
  descarta golpe no vazio, de longe), escolhido pela proporção da base inteira
  (n_defesa ≈ 0,42 × golpes do oponente), não pelas 12 linhas de teste.
- **Avaliação** nas 2 lutas completas do Pan 2023 que estão na base (luta_id 92 e 94; 3 rounds × 2
  atletas = 12 linhas), contra "chutar a média da base" em cada linha:

  | campo | erro médio regras | erro médio chutando a média | correlação |
  |---|---|---|---|
  | t_deslocamento | 13,0 s | 15,3 s | 0,48 |
  | t_ataque | 5,5 s | 5,5 s | 0,20 |
  | t_defesa | 5,8 s | 6,8 s | 0,08 |
  | t_pausa | 14,6 s | 16,8 s | 0,55 |
  | n_ataque | 14,5 | 13,4 | 0,47 |
  | n_defesa | 5,8 | 7,9 | 0,38 |

  As médias batem (ataque 32 × 32 s, pausa 29 × 27 s, defesa 29 × 30 ações), mas a diferença
  round a round ainda é grande. Referência do ruído humano: na base, a pausa do mesmo round difere
  4,8 s em média entre os dois atletas, e deveria ser igual.
- **Onde erra:** (1) pausa no R3 de La Cruz × Keno (base 65–73 s, regras 31 s): advertências do
  árbitro e clinches em close com um atleta só no quadro; (2) n_ataque 18% acima: o contador de
  golpes conta demais e não separa finta (P1); (3) defesa sem subtipo. Estes três são o alvo da E6.
