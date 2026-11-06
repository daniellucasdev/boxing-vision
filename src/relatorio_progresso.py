"""Relatório de progresso do Frami 2.0 em PDF → docs/relatorios/.

Título e arquivo seguem um padrão com a versão do relatório:
  "Frami 2.0 — Relatório de Progresso vX.Y.Z"
  docs/relatorios/Frami2.0_RelatorioProgresso_vX.Y.Z.pdf

Numeração (VERSAO):
  - 0.X.Y enquanto o ponto de chegada não foi alcançado;
  - X = última etapa do caminho principal concluída (E5 → 0.5, E6 → 0.6, E7 → 0.7);
  - Y = revisão do relatório sem etapa nova (números atualizados, lutas novas…);
  - 1.0.0 = ponto de chegada: planilha v2.0 + perfil validados em lutas novas.

Para uma versão nova: atualizar VERSAO, DATA e o texto abaixo, e rodar
  python src/relatorio_progresso.py
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, ListFlowable, ListItem, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

REPO = Path(__file__).resolve().parent.parent
VERSAO = "0.5.0"
DATA = "5 de novembro de 2026"
TITULO = f"Frami 2.0 — Relatório de Progresso v{VERSAO}"
SAIDA = REPO / "docs" / "relatorios" / f"Frami2.0_RelatorioProgresso_v{VERSAO}.pdf"

# cores (mesma paleta das figuras da E2)
INK = colors.HexColor("#0b0b0b")
INK2 = colors.HexColor("#52514e")
GRADE = colors.HexColor("#e4e3df")
FUNDO = colors.HexColor("#f4f3f0")
AZUL = colors.HexColor("#2a78d6")
SITUACAO = {"Pronto": colors.HexColor("#1baf7a"), "Parcial": colors.HexColor("#eda100"),
            "Falta": colors.HexColor("#9a9893"), "Futuro": colors.HexColor("#c9c7c1")}


def _fontes() -> tuple[str, str, str]:
    """Arial (cobre ≈ ≥ → ×); cai para Helvetica se não existir."""
    pasta = Path("/System/Library/Fonts/Supplemental")
    arq = {"Frami": "Arial.ttf", "Frami-Bold": "Arial Bold.ttf", "Frami-Italic": "Arial Italic.ttf"}
    if all((pasta / f).exists() for f in arq.values()):
        for nome, f in arq.items():
            pdfmetrics.registerFont(TTFont(nome, str(pasta / f)))
        pdfmetrics.registerFontFamily("Frami", normal="Frami", bold="Frami-Bold", italic="Frami-Italic",
                                      boldItalic="Frami-Bold")
        return "Frami", "Frami-Bold", "Frami-Italic"
    return "Helvetica", "Helvetica-Bold", "Helvetica-Oblique"


F, FB, FI = _fontes()
S = {
    "titulo": ParagraphStyle("titulo", fontName=FB, fontSize=21, leading=26, textColor=INK),
    "sub": ParagraphStyle("sub", fontName=F, fontSize=11.5, leading=15, textColor=INK2),
    "meta": ParagraphStyle("meta", fontName=F, fontSize=9, leading=12, textColor=INK2),
    "h1": ParagraphStyle("h1", fontName=FB, fontSize=14, leading=18, textColor=INK, spaceBefore=16,
                         spaceAfter=6),
    "h2": ParagraphStyle("h2", fontName=FB, fontSize=11, leading=14, textColor=INK, spaceBefore=10,
                         spaceAfter=4),
    "p": ParagraphStyle("p", fontName=F, fontSize=9.6, leading=13.6, textColor=INK, spaceAfter=5,
                        alignment=TA_LEFT),
    "nota": ParagraphStyle("nota", fontName=FI, fontSize=8.4, leading=11.2, textColor=INK2, spaceAfter=4),
    "cel": ParagraphStyle("cel", fontName=F, fontSize=8.4, leading=10.8, textColor=INK),
    "celb": ParagraphStyle("celb", fontName=FB, fontSize=8.4, leading=10.8, textColor=INK),
    "cab": ParagraphStyle("cab", fontName=FB, fontSize=8.2, leading=10.4, textColor=INK2),
    "destaque": ParagraphStyle("destaque", fontName=F, fontSize=9.6, leading=13.6, textColor=INK),
}


def p(texto: str, estilo: str = "p") -> Paragraph:
    return Paragraph(texto, S[estilo])


def lista(itens: list[str]) -> ListFlowable:
    return ListFlowable([ListItem(p(t), leftIndent=12, value="•") for t in itens], bulletType="bullet",
                        start="•", leftIndent=12, bulletFontName=F, bulletFontSize=9, bulletColor=INK2)


def situacao(rotulo: str) -> Paragraph:
    cor = SITUACAO[rotulo].hexval()[2:]
    return Paragraph(f'<font color="#{cor}">●</font> {rotulo}', S["cel"])


def tabela(cab: list[str], linhas: list[list], larguras: list[float], num: set[int] = frozenset()) -> Table:
    dados = [[Paragraph(c, S["cab"]) for c in cab]]
    for ln in linhas:
        dados.append([c if not isinstance(c, str) else Paragraph(c, S["cel"]) for c in ln])
    t = Table(dados, colWidths=[w * cm for w in larguras], repeatRows=1, hAlign="LEFT")
    estilo = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK2),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, GRADE),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    for c in num:
        estilo.append(("ALIGN", (c, 0), (c, -1), "RIGHT"))
    t.setStyle(TableStyle(estilo))
    return t


def caixa(conteudo: list, largura: float = 17.0) -> Table:
    t = Table([[conteudo]], colWidths=[largura * cm], hAlign="LEFT")
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), FUNDO),
                           ("LINEBEFORE", (0, 0), (0, -1), 2.5, AZUL),
                           ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                           ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return t


def num(x: str) -> Paragraph:
    return Paragraph(x, ParagraphStyle("n", parent=S["cel"], alignment=2))


# ---------------------------------------------------------------------------------------------
# conteúdo
# ---------------------------------------------------------------------------------------------

def conteudo() -> list:
    h = []
    h += [p(TITULO, "titulo"), Spacer(1, 4),
          p("Análise automática de tempo-movimento no boxe olímpico, a partir do vídeo da luta", "sub"),
          Spacer(1, 6),
          p(f"{DATA} · etapa concluída mais recente: E5 (4 estados por regras) · "
            "base de referência: planilha <i>Análises MHdS</i> (anotação manual, v1.0)", "meta"),
          Spacer(1, 10)]

    # 1. resumo
    h.append(caixa([
        p("<b>Em uma página</b>", "destaque"), Spacer(1, 3),
        lista([
            "O Frami 2.0 já transforma o vídeo de uma luta numa <b>pré-planilha</b> no formato da "
            "<i>Análises MHdS</i>: para cada atleta e round, tempo e número de ações em deslocamento, "
            "ataque, defesa e pausa (clinch incluído), com a direção do deslocamento.",
            "Nas 2 lutas completas da base testadas (Pan 2023), as <b>médias batem</b> com a anotação "
            "manual (ataque 32 × 32 s, pausa 29 × 27 s por round), mas o <b>erro round a round ainda é "
            "grande</b>: cerca de 6 s em ataque e defesa e de 13–15 s em deslocamento e pausa. Entre dois "
            "anotadores humanos, a pausa difere 5 s.",
            "Por isso a saída de hoje é uma <b>pré-anotação</b> para um anotador revisar, e não ainda um "
            "resultado final.",
            "Faltam: vídeos completos das lutas da base, um gabarito anotado quadro a quadro, o modelo "
            "temporal para ataque e defesa (E6) e o perfil do lutador (E7).",
        ]),
    ]))

    # 2. ponto de chegada
    h.append(p("1. Ponto de chegada", "h1"))
    h.append(p("Ao final do projeto (versão 1.0.0 deste relatório), o Frami 2.0 deve entregar:"))
    h.append(tabela(
        ["", "O que é"],
        [["<b>Entrada</b>", "Vídeo da transmissão, início de cada round e dados da luta (atletas, cor do "
                            "canto, categoria, fase)."],
         ["<b>Planilha v2.0 automática</b>",
          "1 linha por atleta × round, no layout da <i>Análises MHdS</i>: tempo e número de ações nos 4 "
          "estados (deslocamento, ataque, defesa, pausa com clinch). Mais o detalhamento que a v1.0 não "
          "tem: golpes × fintas; bloqueios × esquivas × guarda; deslocamento para a esquerda/direita "
          "(do ponto de vista do atleta) e para frente/trás em relação ao oponente."],
         ["<b>Perfil do lutador</b>",
          "Pace, explosividade, mobilidade, pressão, engano (fintas), defesa e fadiga do R1 ao R3, cada "
          "um como percentil do atleta dentro do mesmo sexo e categoria na base. Um texto para o técnico, "
          "escrito pelo Claude a partir desses números já calculados (o Claude não mede nada)."],
         ["<b>Critério de sucesso</b>",
          "Em lutas <b>não usadas na calibração</b>: erro por estado dentro da variação entre dois "
          "anotadores humanos (ICC e Bland–Altman); direção do deslocamento conferida contra anotação "
          "quadro a quadro; perfil estável para o mesmo atleta em lutas diferentes."],
         ["<b>Fora do escopo</b>",
          "Tipo de golpe (jab, direto, gancho, uppercut), golpe que acerta × erra e execução num "
          "dispositivo embarcado. Ficam como trabalho futuro (E8)."]],
        [3.6, 13.4]))

    # 3. capacidades
    h.append(p("2. O que o Frami 2.0 faz hoje", "h1"))
    h.append(p("Fluxo atual: vídeo → pose e rastreamento → identidade Vermelho/Azul → compensação da "
               "câmera → golpes e deslocamento → 4 estados por regras → pré-anotação no modo juiz → linha "
               "da planilha. Cada passo abaixo roda sem intervenção, exceto o início dos rounds, que hoje é "
               "informado à mão (cerca de 1 minuto por luta)."))
    h.append(tabela(
        ["Capacidade", "Como funciona", "Situação", "Evidência até agora"],
        [["Pose e rastreamento", "YOLO11-pose (esqueleto de cada pessoa) + ByteTrack", situacao("Pronto"),
          "Roda em lutas inteiras (2 lutas do Pan 2023, 3 rounds cada)."],
         ["Identidade Vermelho/Azul", "Cor do colete, calção e luvas; descarta árbitro e plateia; detecta "
          "cortes de câmera", situacao("Parcial"),
          "~3 erros em 40 quadros conferidos; falta a taxa de erro numa luta inteira."],
         ["Contador de golpes", "Regras sobre velocidade do punho e extensão do braço, por atleta e braço",
          situacao("Parcial"), "Conta ~11 ações a mais por round que a base (~18%); não separa finta."],
         ["Direção do deslocamento", "Desconta o movimento da câmera e o escorço; frente/trás e "
          "esquerda/direita do atleta", situacao("Parcial"),
          "Conferida a olho. Só mede com os pés no quadro (20–28% do round): sai como proporção."],
         ["4 estados por round", "Regras com prioridade Pausa > Ataque > Defesa > Deslocamento; clinch "
          "pela distância entre os pés ou sobreposição dos corpos", situacao("Parcial"),
          "Médias batem com a base; erro por round ainda alto (seção 3)."],
         ["Modo juiz", "Anotação manual na web, vídeo a 0,125×, teclas para estados, ações e direção; "
          "exporta a linha da planilha", situacao("Pronto"),
          "Ferramenta pronta; falta anotar rounds da base para validá-la."],
         ["Pré-anotação", "Estados automáticos abertos no modo juiz para o anotador corrigir",
          situacao("Pronto"), "12 pré-anotações (2 lutas × 3 rounds × 2 atletas) aguardando revisão."],
         ["Base MHdS em dados", "Conversão da planilha por script, com as colunas da v2.0",
          situacao("Pronto"), "786 linhas (132 lutas, 2023–24) + 248 linhas (49 lutas, 2020, só tempos)."],
         ["Estudo estatístico da base", "Modelos mistos, ICC, Bland–Altman, agrupamento de estilos",
          situacao("Pronto"), "Relatório completo em docs/estudo_base.md."],
         ["Interface web", "Análise de clipes com progresso ao vivo, modo juiz, planilha consolidada",
          situacao("Pronto"), "Uso em demonstração."]],
        [3.2, 5.3, 2.0, 6.5]))
    h.append(Spacer(1, 4))
    h.append(p("<b>Ainda não faz:</b> tipo de golpe, alvo (cabeça × corpo), subtipo de defesa (bloqueio, "
               "esquiva, guarda) e separação golpe × finta. Nenhum modelo foi treinado com dados de boxe: o "
               "único modelo é o YOLO-pose genérico; o resto são regras calibradas na base."))

    # 4. resultados
    h.append(p("3. Resultados medidos", "h1"))
    h.append(p("3.1 Estados automáticos × anotação manual", "h2"))
    h.append(p("2 lutas completas do Pan 2023 que estão na base (final 92 kg e semifinal +92 kg): 3 rounds × "
               "2 atletas = 12 linhas. Valores por round."))
    linhas_e5 = [
        ("Tempo em deslocamento (s)", "105,4", "103,2", "13,0", "15,3", "0,46"),
        ("Tempo em ataque (s)", "32,2", "31,9", "5,5", "5,5", "0,20"),
        ("Tempo em defesa (s)", "13,8", "17,8", "5,8", "6,8", "0,05"),
        ("Tempo em pausa, com clinch (s)", "28,6", "27,3", "14,6", "16,8", "0,54"),
        ("Nº de deslocamentos", "58,7", "55,0", "7,3", "7,0", "0,03"),
        ("Nº de ações de ataque", "73,1", "61,8", "14,5", "13,4", "0,34"),
        ("Nº de ações de defesa", "28,9", "29,8", "5,8", "7,9", "0,34"),
        ("Nº de pausas", "10,2", "7,5", "5,0", "4,5", "0,44"),
    ]
    h.append(tabela(["Variável", "Média automático", "Média base", "Erro médio", "Erro de chutar a média",
                     "ICC"],
                    [[a, num(b), num(c), num(d), num(e), num(f)] for a, b, c, d, e, f in linhas_e5],
                    [5.4, 2.4, 2.1, 2.1, 3.0, 2.0], num={1, 2, 3, 4, 5}))
    h.append(p("<i>Erro de chutar a média</i>: o erro de quem preenchesse toda linha com a média da base. O "
               "automático só acrescenta informação quando fica abaixo dele. ICC (concordância absoluta, de 0 "
               "a 1): entre os dois cantos anotados à mão, a pausa tem ICC 0,91.", "nota"))
    h.append(lista([
        "<b>Abaixo do chute</b> em tempo de deslocamento, defesa e pausa e em ações de defesa; empata no "
        "tempo de ataque; pior nas contagens de ataque, deslocamento e pausa.",
        "<b>Onde mais erra:</b> (1) pausa no 3º round da final (base 65–73 s, automático 31 s): advertências "
        "do árbitro e clinches em close, com um atleta só no quadro; (2) golpes a mais, porque o contador "
        "não separa finta nem golpe no vazio; (3) 10 s de pausa no 1º round da semifinal, onde a base tem 0.",
        "<b>Cuidado:</b> são só 12 linhas, e das mesmas lutas usadas para calibrar as regras. O número é "
        "otimista; a avaliação que vale é em lutas novas, que dependem dos vídeos da base.",
    ]))

    h.append(p("3.2 O que a base manual já mostra (estudo E2)", "h2"))
    h.append(Image(str(REPO / "docs/figuras/e2/estados_por_round.png"), width=17 * cm, height=17 * cm * 448 / 1600))
    h.append(p("Tempo médio por round em cada estado, por sexo (média e IC 95%), ciclo de Paris.", "nota"))
    h.append(lista([
        "<b>Cansaço/estratégia:</b> do R1 para o R2/R3 o deslocamento cai ~10 s e a pausa com clinch "
        "sobe ~11–14 s.",
        "<b>Sexo:</b> as mulheres defendem menos (11 × 14 s e 22 × 31 ações por round).",
        "<b>Ciclos olímpicos</b> (eliminatória europeia de 2020 × Pan 2023 + Paris 2024, homens): ataque "
        "+6,3 s e defesa +5,2 s por round (p &lt; 0,001). A diferença se mantém só com quartas em diante.",
        "<b>Vencedor × perdedor:</b> nenhuma variável de tempo ou volume os separa; os juízes pontuam "
        "qualidade, que a planilha não mede.",
        "<b>Piso do erro humano:</b> clinch e pausa valem para os dois atletas, então as linhas dos dois "
        "cantos deveriam ser iguais. Diferem em média 5,0 s na pausa com clinch (ICC 0,91). Essa é a meta "
        "realista para o automático.",
        "<b>Estilos:</b> os atletas formam um contínuo, não grupos separados (silhueta 0,25). O perfil (E7) "
        "vai usar o percentil em cada medida, não rótulos de grupo.",
    ]))

    # 5. o que falta
    h.append(p("4. O que falta", "h1"))
    h.append(tabela(
        ["O que falta", "Por que importa", "Depende de", "Etapa"],
        [["Vídeos completos de 10–15 lutas da base", "Sem eles não há teste em lutas novas; hoje são só 2",
          "Envio dos vídeos (Mateus)", "E0"],
         ["Python 3.10+ no ambiente principal", "Necessário para o relatório pelo Claude",
          "Já testado; falta trocar o ambiente", "E0"],
         ["Revisar as 12 pré-anotações no modo juiz", "Gabarito quadro a quadro: diz se os trechos caem no "
          "momento certo e quanto tempo a pré-anotação economiza", "Anotador humano", "E1 / E5"],
         ["Segundo anotador nos mesmos rounds", "Piso humano para ataque, defesa e deslocamento (a base só "
          "permite medi-lo na pausa)", "Anotador humano", "E1"],
         ["Anotação própria quadro a quadro (~15 lutas, ≈ 36 h)", "Treino e validação do modelo temporal: "
          "finta, tipos de defesa, direção", "Anotadores", "E1 → E6"],
         ["Modelo temporal sobre a pose (TCN/LSTM)", "Ataque e defesa com subtipos; corrige os golpes a mais",
          "Anotação própria + datasets públicos (BoxMAC, BoxingVI)", "E6"],
         ["Pausa em close e advertências do árbitro", "Maior erro da E5", "Gabarito + regra ou modelo novo",
          "E6"],
         ["Perfil do lutador, relatório e tela na web", "É a entrega final", "E5/E6 estáveis", "E7"],
         ["Início dos rounds automático (placar)", "Poupa ~1 min por luta", "Vídeos com placar legível",
          "Opcional"],
         ["Decisões da proposta", "Categorias de peso; métricas (erro médio, ICC e Bland–Altman em vez de "
          "mAP); se a eliminatória de 2020 representa o ciclo de Tóquio", "Orientação", "—"]],
        [4.5, 6.4, 4.2, 1.9]))

    # 6. roteiro
    h.append(KeepTogether([
        p("5. Caminho até o ponto de chegada", "h1"),
        tabela(["Etapa", "Situação", "Pronta quando"],
               [["<b>E0</b> Preparação (base, ambiente, vídeos)", situacao("Parcial"),
                 "Base em dados por script (feito); vídeos de 10–15 lutas em mãos; Python 3.10+"],
                ["<b>E1</b> Modo juiz", situacao("Parcial"),
                 "Anotar 1 round reproduz a linha da base dentro da variação humana"],
                ["<b>E2</b> Estudo da base", situacao("Pronto"), "Capítulo descritivo com figuras (feito)"],
                ["<b>E3</b> Identidade e tempo", situacao("Parcial"),
                 "Trocas de identidade medidas em lutas inteiras"],
                ["<b>E4</b> Deslocamento", situacao("Parcial"),
                 "Direção conferida contra anotação quadro a quadro"],
                ["<b>E5</b> Estados por regras", situacao("Pronto"),
                 "Erro por estado × base medido (feito; precisão a melhorar na E6)"],
                ["<b>E6</b> Modelo temporal", situacao("Falta"), "Supera as regras da E5 no gabarito"],
                ["<b>E7</b> Perfil + relatório", situacao("Falta"),
                 "Perfil gerado para todos os atletas com vídeo → versão 1.0.0"],
                ["<b>E8</b> Tipo de golpe, acerto, on-device", situacao("Futuro"), "Fora do escopo do mestrado"]],
               [5.4, 2.2, 9.4]),
        Spacer(1, 6),
        p("O caminho principal é E0 → E1 → E3 → E5 → E6 → E7. As E3 e E4 funcionam; o que falta nelas é a "
          "conferência em lutas inteiras, que sai junto com o gabarito da E1."),
    ]))

    h.append(Spacer(1, 10))
    h.append(caixa([
        p("<b>Como a versão deste relatório é numerada</b>", "destaque"), Spacer(1, 2),
        p("<b>v0.X.Y</b>: X = última etapa do caminho principal concluída (E5 → 0.5, E6 → 0.6, E7 → 0.7); "
          "Y = revisão sem etapa nova (números atualizados, lutas novas). <b>v1.0.0</b> = ponto de chegada "
          "alcançado. Arquivo: <font name='Courier'>docs/relatorios/Frami2.0_RelatorioProgresso_vX.Y.Z.pdf"
          "</font>, gerado por <font name='Courier'>src/relatorio_progresso.py</font>. Detalhes técnicos: "
          "docs/plano_v2.md, docs/decisoes.md, docs/avaliacao_e5.md e docs/estudo_base.md."),
    ]))
    return h


def _rodape(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont(F, 7.8)
    canvas.setFillColor(INK2)
    canvas.drawString(2 * cm, 1.2 * cm, TITULO)
    canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"página {doc.page}")
    canvas.setStrokeColor(GRADE)
    canvas.setLineWidth(0.5)
    canvas.line(2 * cm, 1.55 * cm, A4[0] - 2 * cm, 1.55 * cm)
    canvas.restoreState()


def main() -> None:
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(SAIDA), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.8 * cm, bottomMargin=2.2 * cm, title=TITULO,
                            author="Frami 2.0", subject="Relatório de progresso do projeto")
    doc.build(conteudo(), onFirstPage=_rodape, onLaterPages=_rodape)
    print(f"→ {SAIDA}")


if __name__ == "__main__":
    main()
