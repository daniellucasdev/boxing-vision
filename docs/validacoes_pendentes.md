# Formulário de validações pendentes

O que ainda **não foi testado ou confirmado** no Boxing Vision. Ficou combinado deixar as
validações finas para o final do projeto; este formulário guarda tudo num lugar só para não se
perder.

**Como preencher:** ao fazer um teste, marque o item no painel abaixo e preencha o bloco dele
(resultado, data, quem, observações). Se falhar, descreva o que aconteceu em *Observações*.

Atualizado em: 2026-10-30

---

## Painel

**1. Modo juiz × base (critério de pronto da E1)**
- [ ] V1 — Reproduzir linhas da base anotando rounds completos
- [ ] V2 — Concordância entre dois anotadores
- [ ] V3 — Tempo real gasto por round anotado
- [ ] V4 — Usabilidade com quem fez a v1.0

**2. Definições a confirmar**
- [ ] D1 — Guarda conta como 1 ação na contagem de defesa?
- [ ] D2 — Pode haver trecho de defesa sem nenhuma ação marcada?
- [ ] D3 — Mudança de direção dentro de um deslocamento
- [ ] D4 — Pausa e repetição devem ser iguais para os dois atletas da luta?

**3. Compatibilidade e robustez**
- [ ] R1 — Safari e Firefox
- [ ] R2 — Vídeo de luta completa (arquivo grande)
- [ ] R3 — Fechar a aba logo depois de marcar
- [ ] R4 — Mesma anotação aberta em duas abas
- [ ] R5 — "Analisar novo clipe" na página inicial depois do redesenho
- [ ] R6 — Tela de notebook (13–14")

**4. Base MHdS**
- [ ] B1 — Linhas duplicadas (copiar/colar)
- [ ] B2 — Agrupamento de lutas (`luta_id`)
- [ ] B3 — Aba de 2020 (só tempos)

**5. Pipeline automático**
- [ ] P1 — Validação humana do contador de golpes (Edwards × Lenzi)
- [ ] P2 — Identidade por cor: taxa de erro numa luta inteira (E3)
- [ ] P3 — Identidade por cor em outras transmissões (Paris 2024, mundiais, uniformes atípicos)
- [ ] P4 — Detector de cortes em outras transmissões
- [ ] P5 — Repetições dentro do round em outras transmissões
- [ ] P6 — Direção do deslocamento × modo juiz (E4)
- [ ] P7 — Limiares do deslocamento (parado, duração mínima)
- [ ] P8 — Escorço de outras câmeras e transmissões
- [ ] P9 — Estados automáticos (E5) × modo juiz, quadro a quadro
- [ ] P10 — Pausa em close e advertências do árbitro (E5)
- [ ] P11 — Limiares da E5 em outras lutas da base

**6. Ambiente**
- [ ] A1 — Python ≥ 3.10 e novo ambiente virtual

---

## 1. Modo juiz × base

### V1 — Reproduzir linhas da base anotando rounds completos

- **O que:** verificar se anotar no modo juiz reproduz a planilha da v1.0.
- **Pré-requisito:** vídeo **completo** dos rounds (não highlight) de pelo menos 2 lutas que estão
  na base. O `data/olympic.mp4` (Edwards × Lenzi) é um resumo com cortes e **não serve**.
- **Como:**
  1. Copiar o vídeo para `data/lutas/` (H.264).
  2. No modo juiz, buscar o atleta na base e escolher o round (isso liga a comparação).
  3. Anotar o round inteiro a 0,125× e marcar o fim.
  4. Anotar a coluna Δ do painel "Comparação com a v1.0" na tabela abaixo.
- **Aceite:** diferença dentro da variação entre anotadores medida em V2. Até V2 existir, usar
  como referência provisória |Δ| ≤ 10% por campo.

| Luta | Atleta | Round | Δ t_desl | Δ t_ataque | Δ t_defesa | Δ t_pausa | Δ n_desl | Δ n_ataque | Δ n_defesa | Δ n_pausa | ok? |
|---|---|---|---|---|---|---|---|---|---|---|---|
| | | | | | | | | | | | |
| | | | | | | | | | | | |
| | | | | | | | | | | | |

- **Resultado:** ☐ ok ☐ falhou · data: ______ · quem: ______
- **Observações:**

### V2 — Concordância entre dois anotadores

- **O que:** medir quanto duas pessoas discordam anotando o mesmo round. Esse é o **teto de
  precisão**: nem o software nem o modo juiz podem ser cobrados por mais do que isso.
- **Indício de que importa:** na própria base, a pausa difere entre os dois atletas da mesma
  luta (Edwards 15,89 s × Lenzi 12,70 s no R1), embora devesse ser igual.
- **Como:** duas pessoas anotam, sem ver o trabalho da outra, os mesmos 3 rounds. Exportar a
  "Linha da planilha" de cada uma e comparar campo a campo.
- **Aceite:** não há; o resultado vira o critério de V1 e da validação da E5.

| Round | Campo com maior diferença | Diferença | Observação |
|---|---|---|---|
| | | | |
| | | | |
| | | | |

- **Resultado:** ☐ feito · data: ______ · anotadores: ______ e ______
- **Observações:**

### V3 — Tempo real gasto por round anotado

- **O que:** a estimativa do plano (~24 min por atleta × round, ~36 h para 15 lutas) foi feita
  no papel.
- **Como:** cronometrar 3 rounds anotados no modo juiz, do play ao fim marcado.
- **Resultado:** round 1: ____ min · round 2: ____ min · round 3: ____ min · média: ____ min
- **Observações:**

### V4 — Usabilidade com quem fez a v1.0

- **O que:** confirmar que a ferramenta é tão prática quanto o processo antigo.
- **Perguntar:** as teclas fazem sentido? 0,125× é a velocidade certa? A direção "do ponto de
  vista do atleta" é fácil de marcar olhando a câmera? Falta alguma marca?
- **Resultado:** ☐ ok ☐ precisa ajustes · data: ______ · quem: ______
- **Observações / pedidos de ajuste:**

---

## 2. Definições a confirmar

Cada item mostra o que está **implementado hoje** em `src/anotacao.py`. Se a resposta for
diferente, a regra precisa mudar.

### D1 — Guarda conta como 1 ação na contagem de defesa?
- **Implementado:** sim. Cada guarda marcada (`R`) soma 1 em `n_defesa`, como bloqueio e esquiva.
- **Resposta:** ☐ sim, está certo ☐ não, a guarda só soma tempo · quem respondeu: ______

### D2 — Pode haver trecho de defesa sem nenhuma ação marcada?
- **Implementado:** pode, mas gera um aviso ("trecho de defesa sem nenhuma ação marcada").
- **Resposta:** ☐ ok assim ☐ deveria ser proibido ☐ o aviso atrapalha · quem: ______

### D3 — Mudança de direção dentro de um deslocamento
- **Implementado:** esquerda → direita sem parar de se deslocar conta **1 deslocamento**
  (`n_deslocamento`), mas **1 para cada direção** (`n_desl_esq`, `n_desl_dir`).
- **Resposta:** ☐ ok ☐ deveria contar 2 deslocamentos · quem: ______

### D4 — Pausa e repetição devem ser iguais para os dois atletas da luta?
- **Implementado:** não. Cada ficha (atleta × round) é anotada de forma independente, como na v1.0.
- **Pergunta:** ao anotar o segundo atleta, a ferramenta deveria copiar as pausas e repetições do
  primeiro? Isso eliminaria a diferença vista em V2, mas muda o processo.
- **Resposta:** ☐ manter independente ☐ copiar do outro atleta · quem: ______

---

## 3. Compatibilidade e robustez

Testado até aqui: só **Google Chrome**, em telas de 1440 e 500 px, com o vídeo `olympic.mp4`
(14 MB) e cerca de 100 marcas.

### R1 — Safari e Firefox
- **Como:** abrir uma anotação; conferir se o vídeo toca a 0,125×, se todas as teclas funcionam,
  se as linhas do tempo aparecem e se o salvamento automático mostra "Salvo ✓".
- **Resultado:** Safari ☐ ok ☐ falhou · Firefox ☐ ok ☐ falhou · data: ______
- **Observações:**

### R2 — Vídeo de luta completa (arquivo grande)
- **Como:** enviar uma luta de ~1 GB pelo botão "Enviar luta" (ver a barra de progresso) e outra
  copiando para `data/lutas/`; navegar pelo vídeo inteiro; anotar um round com 300+ marcas.
- **Aceite:** envio completa; avançar/voltar é imediato; a tela não fica lenta.
- **Resultado:** ☐ ok ☐ falhou · tamanho testado: ______ · data: ______
- **Observações:**

### R3 — Fechar a aba logo depois de marcar
- **Como:** marcar algo e fechar a aba em menos de 1 segundo; reabrir a anotação.
- **Aceite:** a última marca está lá.
- **Resultado:** ☐ ok ☐ perdeu marca · data: ______

### R4 — Mesma anotação aberta em duas abas
- **Limitação conhecida:** vence o último salvamento; marcas feitas na outra aba se perdem.
- **Pergunta:** isso pode acontecer no uso real? Se sim, é preciso uma trava.
- **Resposta:** ☐ não acontece ☐ precisa trava · quem: ______

### R5 — "Analisar novo clipe" na página inicial depois do redesenho
- **O que:** só a página foi testada; um processamento completo não foi rodado depois da mudança.
- **Como:** na página inicial, "Usar clipe de exemplo (12 s)" e esperar o resultado (~2–3 min).
- **Aceite:** a barra avança e o resultado aparece com vídeo, linha do tempo e tabela.
- **Resultado:** ☐ ok ☐ falhou · data: ______
- **Observações:** o vídeo anotado gerado pode sair num formato que o navegador não toca
  (o pipeline cai para MPEG-4 Part 2 quando não há H.264). Anotar se acontecer.

### R6 — Tela de notebook (13–14")
- **Como:** usar o modo juiz por um round inteiro numa tela de notebook.
- **Aceite:** o vídeo, as teclas e o resumo cabem sem rolar a página o tempo todo.
- **Resultado:** ☐ ok ☐ apertado · data: ______

---

## 4. Base MHdS

### B1 — Linhas duplicadas (copiar/colar)
- **Situação:** o documento da base lista linhas copiadas (Jalolov R2 = R3 na final; R1 de
  Khyzhniak × Souza copiado de Dusmatov; Chaloyan R1 = Ghadfa R2; Lai Chu R1 = Hasanov R3;
  Congo Chala R1 = Uulu R3; Jack R1 = Boltaev R3; alguns rounds femininos). A conversão ainda
  **não** remove nem marca essas linhas.
- **Decisão:** ☐ excluir ☐ marcar com uma coluna ☐ corrigir na planilha original · quem: ______

### B2 — Agrupamento de lutas (`luta_id`)
- **Situação:** a conversão encontrou 132 lutas agrupando por competição + fase + categoria + nomes.
  Grafias diferentes do mesmo atleta separam a mesma luta (ex.: o oponente de Lazizbek aparece
  como "Mundyk").
- **Como:** conferir no CSV se cada `luta_id` tem exatamente 6 linhas (3 rounds × 2 atletas).
- **Resultado:** lutas com ≠ 6 linhas: ______ · ☐ corrigido · data: ______

### B3 — Aba de 2020 (só tempos)
- **Situação:** a aba "Pré olímpico 2020" (248 rounds, sem contagens, categorias antigas) não é
  convertida.
- **Decisão:** ☐ converter ☐ não usar · quem: ______

---

## 5. Pipeline automático

### P1 — Validação humana do contador de golpes (Edwards × Lenzi)
- **Situação:** o contador por regras (Fase 1) foi executado, mas nunca comparado com uma contagem
  humana.
- **Como:** anotar o próprio `olympic.mp4` no modo juiz só com `G`/`F` para cada atleta e comparar
  com o total de golpes por atleta do contador. É um highlight, então serve para golpes, **não**
  para tempos de round.
- **Resultado:** humano ____ × contador ____ (atleta A) · humano ____ × contador ____ (atleta B)
- **Observações:**

### P2 — Identidade por cor: taxa de erro numa luta inteira (E3)
- **Situação:** conferido a olho em amostras (40 quadros por vídeo) de 3 vídeos; nunca numa
  luta inteira com contagem sistemática.
- **Como:** rodar `src/features.py --save` numa luta completa da base, assistir o
  `annotated.mp4` e contar, a cada 10 s, se os rótulos Vermelho/Azul estão nos atletas certos
  (erro = rótulo em outra pessoa ou no atleta trocado).
- **Aceite:** ≥ 95% dos rótulos certos nos quadros em que aparecem.
- **Resultado:** acertos ____ / ____ · data: ______
- **Observações:**

### P3 — Identidade por cor em outras transmissões
- **Situação:** limiares de cor calibrados no Pan 2023 (ringue azul), Tóquio 2020 (arquibancada
  vermelha, colete azul-marinho) e Paris 2024 (`olympic.mp4`, highlight). Não testado: mundiais,
  qualificatórios, iluminação diferente, uniforme com estampa grande (o calção do Edwards em
  Paris é estampado em rosa).
- **Como:** repetir a sonda de cor em 1 luta de cada transmissão nova.
- **Resultado:** ☐ ok ☐ precisou recalibrar · transmissões testadas: ______

### P4 — Detector de cortes em outras transmissões
- **Situação:** limiar (diferença média de pixels ≥ 0,12) calibrado na final do Pan 2023: pegou
  27 de 27 cortes conferidos a olho; os falsos positivos são vinhetas e uma panorâmica rápida.
- **Como:** mesma conferência visual numa transmissão de Paris 2024 ou de mundial.
- **Resultado:** cortes detectados ____ / conferidos ____ · falsos ____

### P5 — Repetições dentro do round em outras transmissões
- **Situação:** na final do Pan 2023 as repetições só aparecem no intervalo, entre vinhetas do
  logo. Se outra transmissão repetir lances **durante** o round, o relógio do round precisa
  descontá-las (detectar a vinheta).
- **Como:** assistir 1 round inteiro de Paris 2024 e de um mundial.
- **Resultado:** ☐ só no intervalo ☐ também dentro do round · transmissões: ______

### P6 — Direção do deslocamento × modo juiz (E4)
- **Situação:** a direção automática (frente/trás/esquerda/direita) foi conferida só a olho: das
  12 amostras com fundo alinhado, 8 claramente certas, 1 plausível e 3 duvidosas, todas com os pés
  cortados na borda da tela (agora descartados). Falta a comparação com anotação humana.
- **Como:** no modo juiz, anotar o deslocamento com as setas em 2 rounds da final La Cruz × Keno.
  Rodar `src/features.py` no mesmo vídeo e comparar, nos trechos com os pés visíveis, a
  proporção de tempo em cada direção e a concordância quadro a quadro.
- **Resultado:** concordância ______% · maior confusão: ______ → ______ · ☐ aceitável ☐ ajustar

### P7 — Limiares do deslocamento (parado, duração mínima)
- **Situação:** "parado" abaixo de 0,25 corpo/s (~0,45 m/s), trecho mínimo de 0,2 s e janela de
  0,5 s foram escolhidos por bom senso, não calibrados.
- **Como:** com a anotação do P6, variar os 3 valores e escolher os que mais concordam com o juiz;
  conferir também se `n_` (nº de trechos) bate com a contagem humana.
- **Resultado:** parado ______ corpo/s · trecho mínimo ______ s · janela ______ s

### P8 — Escorço de outras câmeras e transmissões
- **Situação:** o achatamento da profundidade (0,33) foi medido pelos cantos do ringue na câmera
  principal do Pan 2023. Câmeras mais baixas (beira do ringue) e outras arenas podem ter outro
  valor; com o valor errado, frente/trás e esquerda/direita se misturam quando os atletas estão
  um na frente do outro.
- **Como:** num plano aberto de Paris 2024 e de Tóquio 2020, anotar os 4 cantos do ringue e
  calcular o escorço como em `docs/decisoes.md` (E4).
- **Resultado:** Paris ______ · Tóquio ______ · ☐ uma constante serve ☐ precisa por transmissão

### P9 — Estados automáticos (E5) × modo juiz, quadro a quadro
- **Situação:** a E5 só foi comparada com os **totais** da base por round (12 linhas, 2 lutas do
  Pan 2023). As médias batem, mas não se sabe se os trechos caem nos mesmos momentos.
- **Como:** gerar a pré-anotação com `src/estados.py --gravar` (ver README), abrir no modo juiz e
  corrigir um round inteiro. Comparar a pré-anotação com a corrigida: % do tempo no mesmo estado e
  matriz de confusão entre os 4 estados. A correção também mede quanto tempo a pré-anotação
  economiza em relação a anotar do zero (V3).
- **Resultado:** concordância ______% · maior confusão: ______ → ______ · tempo de correção ______ min/round

### P10 — Pausa em close e advertências do árbitro (E5)
- **Situação:** no R3 de La Cruz × Keno a base marca 65–73 s de pausa e as regras, 31 s. Nos
  quadros do erro aparecem advertências (árbitro com um atleta só no quadro) e clinches em close
  em que o YOLO junta os dois atletas. Nenhuma regra simples pegou as advertências.
- **Como:** listar os trechos de pausa da base desse round no modo juiz (P9) e classificar os
  perdidos: advertência, clinch em close, contagem, outro.
- **Resultado:** advertência ______ s · clinch em close ______ s · outros ______ s

### P11 — Limiares da E5 em outras lutas da base
- **Situação:** clinch (0,45 corpo; 45% de sobreposição), janela do ataque (±0,25 s) e alcance da
  defesa foram calibrados em proporções da base inteira e conferidos só em 2 lutas, da mesma
  transmissão.
- **Como:** baixar ao menos 2 lutas da base de outra competição (ver `docs/fontes_videos.md`),
  rodar o pipeline + `src/estados.py --luta-id`, e comparar o erro com a tabela da E5 em
  `docs/decisoes.md`.
- **Resultado:** erro médio t_pausa ______ s · t_defesa ______ s · ☐ segue igual ☐ recalibrar

---

## 6. Ambiente

### A1 — Python ≥ 3.10 e novo ambiente virtual
- **Situação:** o projeto roda em Python 3.9.6 (o do macOS). A integração com o Claude (E7) exige
  ≥ 3.10.
- **Como:** instalar o Python 3.12, recriar o `.venv`, `pip install -r requirements.txt`, abrir a
  interface web e rodar `src/features.py` num clipe.
- **Resultado:** ☐ ok · versão: ______ · data: ______

---

## Já testado (referência)

- Regras de contagem do modo juiz com um round sintético de resultado conhecido (tempos,
  trechos, direções, golpes × fintas, avisos).
- API do servidor: criar, salvar, ler, apagar, os 3 CSVs, planilha completa, busca na base,
  bloqueio de caminhos fora de `data/`.
- Fluxo de teclado num Chrome real: todas as teclas, troca automática de estado, repetir tecla,
  desfazer, repetição fora do tempo, bloqueio depois do fim, relógio do round, salvamento automático.
- Conversão da base: 786 rounds, 132 lutas, todas as categorias com código; os 7 rounds fora de
  175–185 s são os já conhecidos como erro de cronometragem.
- Identidade por cor: casamento em 6 cenários sintéticos (comissão no corner, plateia ao fundo,
  clinch, memória vencida, cinegrafista, cor do outro canto); 27/27 cortes de câmera conferidos.
- Estados automáticos (E5) contra os totais da base nas 2 lutas completas do Pan 2023 (12 linhas):
  médias batem; erro por linha abaixo de chutar a média em t_desl, t_defesa, t_pausa e n_defesa
  (tabela em `docs/decisoes.md`). Pipeline → `src/estados.py` → resumo testado de ponta a ponta
  num trecho de 20 s.
- Compensação da câmera: movimento conhecido (pan, tilt + zoom, parada, pan lento) com placar
  fixo na tela, erro < 0,1 px; em vídeo real, o fundo alinhado muda 39–49% menos e os quadros
  dados como "câmera parada" têm o fundo de fato parado.
- Direções: atleta olhando para a direita, para o fundo e para a câmera (esquerda/direita do
  ponto de vista do atleta); atleta parado durante um pan dá velocidade zero.
