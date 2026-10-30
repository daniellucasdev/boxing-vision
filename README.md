# Frami 2.0 🥊

Visão computacional para **boxe olímpico**: a partir do vídeo da luta, medir por atleta e por
round quanto tempo ele passa **se deslocando, atacando, defendendo ou em pausa**, contar as ações
de cada estado, medir a **direção do deslocamento** (esquerda/direita, frente/trás) e montar um
**perfil de estilo** de cada lutador (explosivo, volume, pressão, móvel…).

Projeto de mestrado. Plano completo: [docs/plano_v2.md](docs/plano_v2.md).

## De onde vem: v1.0 (manual) → v2.0 (este software)

- **v1.0:** um juiz assistia à luta 8× mais devagar, cronometrava cada estado e preenchia a
  planilha *Análises MHdS*. Ela tem 786 rounds de 2023–2024 (Olimpíadas 2024 + Pan 2023) e 248
  de 2020 (só tempo).
- **v2.0:** o software gera **a mesma planilha automaticamente**, e a base da v1.0 passa a ser
  ground truth e referência de pace.

### Saída: 1 linha por atleta × round

| Estado | `t_` (s) | `n_` |
|---|---|---|
| Deslocamento | tempo andando pelo ringue **sem atacar**, procurando abertura | nº de trechos contínuos de deslocamento |
| Ataque | tempo em ação ofensiva | golpes + fintas |
| Defesa | tempo defendendo, incluindo guarda fechada | bloqueios + esquivas + guarda |
| **Pausa** | luta parada **+ clinch** | nº de pausas + clinches |

Os estados são mutuamente exclusivos e somam ≈ 180 s por round (tempo de luta; as repetições
da transmissão ficam de fora). Atacar enquanto se desloca conta como **ataque**. **Na v2.0 o
clinch conta como pausa** (na v1.0 era um estado separado). Colunas novas: detalhamento do ataque (golpes × fintas) e da
defesa (bloqueios × esquivas × guarda), e tempo e contagem de deslocamento **para a
esquerda/direita** (do ponto de vista do atleta) e **para frente/trás** em relação ao oponente.

## Estado atual

| | Situação |
|---|---|
| Pose + tracking (YOLO11-pose + ByteTrack) | ✅ |
| **Identidade pela cor do canto** (Vermelho/Azul, medida no colete, calção e luvas) + detector de cortes de câmera (`src/identidade.py`) | ✅ ~3 erros em 40 quadros nos rounds; taxa de erro na luta inteira pendente |
| Contador de golpes por regras (sem tipo de golpe), por atleta e braço | ✅ executado em Edwards × Lenzi (Olimpíadas 2024); validação humana pendente |
| Interface web (estilo Netflix, paleta azul) | ✅ |
| Base MHdS em CSV, com colunas v2.0 (`src/base_mhds.py`) | ✅ 786 rounds, 132 lutas |
| **Modo juiz**: anotação manual com timestamps → planilha v2.0 + comparação com a base | ✅ ferramenta pronta; validação (anotar rounds da base) pendente |
| **Direção do deslocamento** automática: câmera descontada, frente/trás e esquerda/direita do atleta (`src/deslocamento.py`) | ✅ conferida a olho; comparação com o modo juiz pendente. Mede só com os pés no quadro (~20–28% do round) |
| **4 estados automáticos** por regras → pré-anotação no modo juiz (`src/estados.py`) | ✅ médias batem com a base nas 2 lutas testadas; por round, erro de ~6 s em ataque/defesa e ~15 s em pausa/deslocamento. Defesa sem subtipo, golpe sem separar finta |
| Perfil do lutador | ⏳ planejado ([plano](docs/plano_v2.md)) |

## Roadmap

- [x] **Fase 0:** YOLO-pose + tracking em vídeo de luta
- [x] **Fase 1:** features de pose (velocidade do punho, extensão do braço, distância à cabeça do
  oponente) + contador de golpes por regras com refratário; slots A/B com gating
- [ ] **E0:** ~~base MHdS em CSV por script~~ ✅; Python ≥ 3.10; vídeos completos das lutas da base
- [x] **E1:** *modo juiz* na web: anotação a 0,125× com timestamps, exportando no layout da planilha
  (falta o critério de pronto: anotar rounds da base e comparar)
- [ ] **E2:** estudo da base (pace por categoria/sexo/round, agrupamentos de estilo), em paralelo
- [x] **E3:** identidade por cor do colete (azul/vermelho) e cortes de câmera; rounds marcados no
  modo juiz (as repetições da TV só aparecem nos intervalos; detecção automática fica para depois)
- [x] **E4:** deslocamento: compensação de câmera + frente/trás/esquerda/direita (proporções do
  tempo com os pés visíveis; limiares a calibrar com o modo juiz)
- [x] **E5:** 4 estados por regras → pré-anotação no modo juiz → planilha v2.0 (ataque e defesa
  sem subcategorias; precisão por round a melhorar na E6)
- [ ] **E6:** modelo temporal (TCN/LSTM) sobre pose para ataque e defesa
- [ ] **E7:** perfil do lutador + relatório em texto (Claude)
- [ ] **E8 (futuro):** tipo de golpe, golpe certo/errado, YOLO quantizado on-device (ESP32-S3)

## Dados

### Base de referência própria (v1.0)

Planilha *Análises MHdS 2026-atual.xlsx*, com 3 abas: "Olimpico e Pre-2024", "Pré olímpico 2020"
e "Códigos". Fica em `data/referencia/` (fora do git) e é convertida em
`data/referencia/rounds_2023_2024.csv`. A conversão padroniza grafias, fases e categorias (com o
código da aba "Códigos"), recalcula o total como a soma dos 5 tempos (a coluna "Total" foi digitada
e às vezes diverge) e acrescenta `t_pausa_v2`/`n_pausa_v2` (clinch + pausa). A aba de 2020, que só
tem tempos, ainda não é convertida.

### Datasets públicos

Nenhum dataset público rotula **deslocamento** nem **fintas** de boxeadores: a direção do
deslocamento é medida por geometria (tracking + compensação de câmera), e ambos são validados com
anotação própria (E1).

| Dataset | Rótulos | Uso no projeto |
|---|---|---|
| **BoxMAC** ([arXiv 2412.18204](https://arxiv.org/abs/2412.18204)) | 13 por frame: jab, cross, lead/rear hook, lead/rear uppercut, stance, **slip, block, guard, duck, clinching**, no action. Boxe profissional, 4 câmeras PTZ | Defesa (slip/duck → esquiva, block → bloqueio, guard → guarda) e clinch. Disponibilidade pública não confirmada |
| **BoxingVI** ([arXiv 2511.16524](https://arxiv.org/abs/2511.16524)) | 6.915 clipes, 6 golpes: jab, cross, lead/rear hook, lead/rear uppercut. Pose 2D incluída; sparring do YouTube. Sem defesas e sem alvo | Detecção de ataque; tipo de golpe (futuro) |
| **Olympic Boxing Punch Classification** (Stefański et al., [Entropy 2024](https://doaj.org/article/95fc84c03185481199c08b8aa53726b2); [versão HF](https://huggingface.co/datasets/NealBeans/BoxingDataset)) | 2.278 clipes de boxe **olímpico**, 8 classes: cabeça / corpo / bloqueado / errou × mão esquerda/direita. Sem tipo de golpe | Domínio olímpico; desfecho do golpe (futuro). Uso só acadêmico |
| **SportsMOT** ([GitHub](https://github.com/MCG-NJU/SportsMOT)) | Tracking de atletas (basquete, vôlei, futebol) | Opcional: avaliar o rastreador |

Código de referência (não é dataset): [ACM40960/Boxing](https://github.com/ACM40960/Boxing),
YOLO11-pose + LSTM para golpes (jab, cross, hook, uppercut) e bloqueios (antebraço, guarda alta,
aparada).

## Configuração

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # e preencha ANTHROPIC_API_KEY (só necessário a partir da E7)
```

> ⚠️ A integração com o Claude (E7) exige **Python ≥ 3.10**. O Python do sistema macOS é 3.9:
> instale o 3.12 (python.org ou Homebrew) e recrie o `.venv` com ele.

O `.env` guarda `ANTHROPIC_API_KEY` e `CLAUDE_MODEL` (padrão `claude-opus-5-5`) e **não** vai
para o git. O Claude só escreve o relatório de perfil a partir das métricas já calculadas; ele não
participa da medição.

## Como rodar

```bash
# E0: base de referência (uma vez, ou quando a planilha mudar)
python src/base_mhds.py --xlsx "data/referencia/Análises MHdS 2026-atual.xlsx"
```

### Modo juiz (E1)

Abra a interface web (abaixo) → **Modo juiz**. Escolha o vídeo, busque o atleta na base (isso
preenche os dados e liga a comparação com a v1.0) e anote o round a 0,125×:

| Tecla | Marca |
|---|---|
| `1` / `←` `→` `↑` `↓` | deslocamento (sem direção / esquerda, direita, frente, trás — **do ponto de vista do atleta**) |
| `2` `3` `4` | ataque, defesa, pausa (inclui clinch) |
| `0` | fora: repetição da TV ou corte (não conta no tempo do round) |
| `Enter` | fim do round |
| `G` `F` | golpe, finta (abrem o estado de ataque se preciso) |
| `B` `E` `R` | bloqueio, esquiva, guarda (abrem o estado de defesa se preciso) |
| `⌫` | desfazer · `espaço` tocar/pausar · `Z`/`X` ±2 s · `,`/`.` quadro a quadro · `[`/`]` velocidade |

Tudo é salvo automaticamente em `data/anotacoes/` (1 JSON por atleta × round, **fora do git** —
faça backup). Exporta a linha da planilha, os intervalos e as ações em CSV; **Planilha v2.0** no menu
junta todas as anotações. Vídeos novos podem ser enviados pela página ou copiados para
`data/lutas/`; precisam estar em H.264 para tocar no navegador.

### Pipeline automático

```bash
# Fase 0: pose + tracking (vídeo anotado em runs/)
python src/run_pose.py --source data/video.mp4 --save

# Fase 1 + E3 + E4: golpes e deslocamento por canto Vermelho/Azul
# (outputs/features.csv, deslocamento.csv, eventos.json, serie.npz, annotated.mp4)
python src/features.py --source data/video.mp4 --save

# E5: 4 estados por round (início de cada round em segundos do vídeo); --luta-id liga a
# comparação com a base; --gravar salva as pré-anotações para abrir no modo juiz
python src/estados.py --resultado outputs --rounds 49 289.2 529.3 --luta-id 94 \
    --video lutas/pan2023_final_92kg_lacruz_x_keno.mp4 --gravar
```

### Interface web (demonstração)

```bash
# opção 1: duplo-clique em scripts/start_web.command (Finder)
# opção 2: terminal
source .venv/bin/activate
python src/webapp.py                # http://127.0.0.1:5000
python src/webapp.py --host 0.0.0.0 # acessível de outro aparelho na rede
```

O início mostra a luta pré-analisada, as anotações em andamento e os vídeos disponíveis, e permite
analisar clipes novos (upload ou clipe de exemplo de 12 s) com barra de progresso ao vivo.

## Estrutura

```
boxing-vision/
├── src/
│   ├── run_pose.py      # Fase 0: pose + tracking em vídeo
│   ├── features.py      # Fase 1: features de pose + contador por regras (CLI + run_pipeline)
│   ├── identidade.py    # E3: cor do canto pelo corpo + detector de cortes de câmera
│   ├── deslocamento.py  # E4: movimento da câmera + direção do deslocamento
│   ├── estados.py       # E5: 4 estados por regras → pré-anotação do modo juiz
│   ├── analyze.py       # job de análise p/ web (progress.json + result.json)
│   ├── base_mhds.py     # E0: planilha MHdS (xlsx) → CSV com colunas v2.0
│   ├── anotacao.py      # E1: marcas do modo juiz → linha da planilha v2.0 + avisos
│   ├── webapp.py        # interface web Flask (início + modo juiz + API)
│   ├── static/          # app.css (visual), juiz.css + juiz.js (modo juiz)
│   └── templates/       # base.html, index.html, juiz.html
├── scripts/
│   └── start_web.command  # inicia a web (duplo-clique no Finder)
├── docs/
│   ├── plano_v2.md      # plano do mestrado (v2.0)
│   ├── validacoes_pendentes.md  # formulário do que falta testar/confirmar
│   ├── fontes_videos.md # origem dos vídeos de teste (data/lutas/)
│   └── decisoes.md      # registro de decisões
├── data/                # fora do git: vídeos, lutas/, referencia/ (base MHdS), anotacoes/
├── models/              # pesos (fora do git)
├── outputs/             # vídeos anotados e resultados (fora do git)
├── .env.example         # modelo do .env (chave do Claude)
└── .env                 # chave do Claude (fora do git)
```
