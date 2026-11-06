"""E2 — estudo da base MHdS: ritmo, ciclos × sexo, vencedor × perdedor, confiabilidade e estilos.

Lê os dois CSVs gerados por base_mhds.py:
  - rounds_2023_2024.csv: Pan 2023 + Paris 2024, tempos e contagens;
  - rounds_2020.csv: eliminatória europeia para Tóquio 2020, só tempos.

Gera docs/estudo_base.md (tabelas + texto) e as figuras em docs/figuras/e2/. Tudo sai da base
manual (v1.0): é a referência da v2.0 automática e responde ao objetivo de comparar sexos e
ciclos olímpicos.

Notas de método:
  - modelos mistos (statsmodels MixedLM) com intercepto aleatório por luta: os 6 rounds de uma
    luta (3 × 2 atletas) não são independentes;
  - p-valores corrigidos por Holm dentro de cada família (as variáveis de uma mesma tabela);
  - confiabilidade da anotação: clinch e pausa são eventos dos DOIS atletas, então as duas linhas
    do mesmo round deveriam ter o mesmo valor. A diferença entre elas é um piso do erro humano
    (ICC de concordância absoluta e Bland–Altman);
  - estilos: k-means sobre o perfil médio de cada atleta em cada luta (só 2023–2024, que tem
    contagens), com k escolhido pela silhueta.

CLI:
  python src/estudo_base.py
"""

from __future__ import annotations

import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import statsmodels.formula.api as smf  # noqa: E402
from scipy import stats  # noqa: E402
from sklearn.cluster import KMeans  # noqa: E402
from sklearn.metrics import silhouette_score  # noqa: E402

from base_mhds import ABA_2020, CSV_2020, CSV_PADRAO, REPO  # noqa: E402

DOC = REPO / "docs" / "estudo_base.md"
FIG = REPO / "docs" / "figuras" / "e2"

COMPETICOES = {"Eliminatória europa": "Pré-olímpico 2020", "Panamericano 2023": "Pan 2023",
               "Olimpiadas 2024": "Paris 2024"}
ORDEM_COMP = ["Pré-olímpico 2020", "Pan 2023", "Paris 2024"]
ESTADOS = [("t_deslocamento", "Deslocamento"), ("t_ataque", "Ataque"), ("t_defesa", "Defesa"),
           ("t_pausa_v2", "Pausa (com clinch)")]
TEMPOS = ["t_deslocamento", "t_ataque", "t_defesa", "t_clinch", "t_pausa", "t_pausa_v2"]
CONTAGENS = ["n_deslocamento", "n_ataque", "n_defesa", "n_clinch", "n_pausa", "n_pausa_v2"]
NOME = {"t_deslocamento": "t deslocamento (s)", "t_ataque": "t ataque (s)", "t_defesa": "t defesa (s)",
        "t_clinch": "t clinch (s)", "t_pausa": "t pausa (s)", "t_pausa_v2": "t pausa v2.0 (s)",
        "n_deslocamento": "n deslocamento", "n_ataque": "n ataque", "n_defesa": "n defesa",
        "n_clinch": "n clinch", "n_pausa": "n pausa", "n_pausa_v2": "n pausa v2.0"}

# paleta de referência (skill dataviz): categóricas na ordem fixa, tinta neutra para texto
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
SUPERFICIE, TINTA, TINTA_2, GRADE = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"


# ---------------------------------------------------------------- dados

def carregar() -> pd.DataFrame:
    df = pd.concat([pd.read_csv(CSV_PADRAO), pd.read_csv(CSV_2020)], ignore_index=True)
    df["comp"] = df["competicao"].map(COMPETICOES)
    df["ciclo"] = np.where(df["fonte"] == ABA_2020, "Tóquio", "Paris")
    df["vencedor"] = (df["resultado"] == "Vencedor").astype(int)
    return df


def fmt(x: float, casas: int = 1) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    return f"{x:.{casas}f}".replace(".", ",")


def fmt_p(p: float) -> str:
    return "< 0,001" if p < 0.001 else fmt(p, 3)


def holm(ps: list[float]) -> list[float]:
    ordem = np.argsort(ps)
    m, out, ac = len(ps), [0.0] * len(ps), 0.0
    for i, j in enumerate(ordem):
        ac = max(ac, min(1.0, (m - i) * ps[j]))
        out[j] = ac
    return out


def tabela(cab: list[str], linhas: list[list[str]]) -> str:
    out = ["| " + " | ".join(cab) + " |", "|" + "|".join("---" for _ in cab) + "|"]
    out += ["| " + " | ".join(l) + " |" for l in linhas]
    return "\n".join(out)


def misto(formula: str, dados: pd.DataFrame, grupo: str = "luta_id"):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return smf.mixedlm(formula, dados, groups=dados[grupo]).fit(reml=True)


def pares_cantos(df: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por round com as duas colunas Vermelho/Azul de cada variável."""
    chave = ["fonte", "luta_id", "round"]
    v = df[df["cor"] == "Vermelho"].drop_duplicates(chave).set_index(chave)
    a = df[df["cor"] == "Azul"].drop_duplicates(chave).set_index(chave)
    return v.merge(a, left_index=True, right_index=True, suffixes=("_v", "_a")).reset_index()


def icc_a1(x: np.ndarray, y: np.ndarray) -> float:
    """ICC(A,1): dois avaliadores, efeitos aleatórios, concordância absoluta, medida única."""
    m = np.column_stack([x, y])
    n, k = m.shape
    media = m.mean()
    msr = k * ((m.mean(axis=1) - media) ** 2).sum() / (n - 1)
    msc = n * ((m.mean(axis=0) - media) ** 2).sum() / (k - 1)
    mse = ((m - m.mean(axis=1, keepdims=True) - m.mean(axis=0, keepdims=True) + media) ** 2).sum() \
        / ((n - 1) * (k - 1))
    return (msr - mse) / (msr + (k - 1) * mse + k * (msc - mse) / n)


# ---------------------------------------------------------------- figuras

def _eixo(ax) -> None:
    ax.set_facecolor(SUPERFICIE)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(GRADE)
    ax.tick_params(colors=TINTA_2, labelsize=9)
    ax.grid(color=GRADE, linewidth=0.8)
    ax.set_axisbelow(True)


def fig_estados(df: pd.DataFrame) -> str:
    grupos = [(c, s) for c in ORDEM_COMP for s in ("Masculino", "Feminino")]
    medias = [df[(df["comp"] == c) & (df["sexo"] == s)][[e for e, _ in ESTADOS]].mean() for c, s in grupos]
    fig, ax = plt.subplots(figsize=(8, 3.6), facecolor=SUPERFICIE)
    _eixo(ax)
    ax.grid(axis="y", visible=False)
    y = np.arange(len(grupos))[::-1]
    esq = np.zeros(len(grupos))
    for (col, rot), cor in zip(ESTADOS, SERIES):
        larg = np.array([m[col] for m in medias])
        ax.barh(y, larg, left=esq, color=cor, height=0.62, edgecolor=SUPERFICIE, linewidth=2, label=rot)
        esq += larg
    ax.set_yticks(y, [f"{c} · {s[0]}" for c, s in grupos], color=TINTA)
    ax.set_xlim(0, 185)
    ax.set_xlabel("segundos por round (média)", color=TINTA_2, fontsize=9)
    ax.legend(ncol=4, loc="lower left", bbox_to_anchor=(0, 1.0), frameon=False, fontsize=9,
              labelcolor=TINTA)
    fig.tight_layout()
    caminho = FIG / "estados_por_competicao.png"
    fig.savefig(caminho, dpi=160)
    plt.close(fig)
    return caminho.name


def fig_rounds(df: pd.DataFrame) -> str:
    fig, eixos = plt.subplots(1, 4, figsize=(10, 2.8), facecolor=SUPERFICIE)
    for ax, (col, rot) in zip(eixos, ESTADOS):
        _eixo(ax)
        for s, cor in (("Masculino", SERIES[0]), ("Feminino", SERIES[1])):
            g = df[df["sexo"] == s].groupby("round")[col]
            m, ep = g.mean(), 1.96 * g.std() / np.sqrt(g.count())
            ax.errorbar(m.index, m.values, yerr=ep.values, color=cor, linewidth=2, marker="o",
                        markersize=5, capsize=3, label=s)
        ax.set_title(rot, color=TINTA, fontsize=10, loc="left")
        ax.set_xticks([1, 2, 3], ["R1", "R2", "R3"])
        ax.set_xlim(0.8, 3.2)
    eixos[0].set_ylabel("segundos (média ± IC 95%)", color=TINTA_2, fontsize=9)
    eixos[0].legend(frameon=False, fontsize=8, labelcolor=TINTA, loc="best")
    fig.tight_layout()
    caminho = FIG / "estados_por_round.png"
    fig.savefig(caminho, dpi=160)
    plt.close(fig)
    return caminho.name


def fig_bland_altman(p: pd.DataFrame, col: str, rot: str) -> str:
    x, y = p[f"{col}_v"].to_numpy(), p[f"{col}_a"].to_numpy()
    media, dif = (x + y) / 2, x - y
    vies, dp = dif.mean(), dif.std(ddof=1)
    fig, ax = plt.subplots(figsize=(6, 3.6), facecolor=SUPERFICIE)
    _eixo(ax)
    ax.scatter(media, dif, s=14, color=SERIES[0], alpha=0.55, edgecolors="none")
    for v, txt, est in ((vies, f"viés {fmt(vies)} s", "-"), (vies + 1.96 * dp, f"+1,96 DP {fmt(vies + 1.96 * dp)} s", "--"),
                        (vies - 1.96 * dp, f"−1,96 DP {fmt(vies - 1.96 * dp)} s", "--")):
        ax.axhline(v, color=TINTA_2, linewidth=1, linestyle=est)
        ax.annotate(txt, (media.max(), v), color=TINTA_2, fontsize=8, ha="right", va="bottom")
    ax.set_xlabel(f"{rot}: média dos dois cantos (s)", color=TINTA_2, fontsize=9)
    ax.set_ylabel("Vermelho − Azul (s)", color=TINTA_2, fontsize=9)
    fig.tight_layout()
    caminho = FIG / f"bland_altman_{col}.png"
    fig.savefig(caminho, dpi=160)
    plt.close(fig)
    return caminho.name


# ---------------------------------------------------------------- seções

def secao_amostra(df: pd.DataFrame) -> str:
    linhas = []
    for c in ORDEM_COMP:
        d = df[df["comp"] == c]
        por_sexo = [f"{d[d['sexo'] == s]['luta_id'].nunique()} / {len(d[d['sexo'] == s])}"
                    for s in ("Masculino", "Feminino")]
        fases = ", ".join(f"{f} {n}" for f, n in d.groupby("fase")["luta_id"].nunique().items())
        linhas.append([c, *por_sexo, "sim" if d["n_ataque"].notna().any() else "não", fases])
    cantos = pares_cantos(df)
    return "\n".join([
        "## 1. Amostra", "",
        tabela(["Competição", "Masc. (lutas / linhas)", "Fem. (lutas / linhas)", "Contagens?", "Lutas por fase"], linhas),
        "",
        f"Total: {df['luta_id'].nunique()} lutas, {len(df)} linhas (atleta × round). "
        f"Em {len(cantos)} rounds os dois cantos foram anotados (base da seção 6). "
        "**Tóquio 2020 não está na base**; o ciclo de Tóquio é representado pela eliminatória "
        "europeia de 2020, que só tem quartas, semifinais e finais e não tem contagens.",
    ])


def secao_perfil(df: pd.DataFrame) -> tuple[str, str]:
    d = df[df["ciclo"] == "Paris"]
    linhas = []
    for col in TEMPOS + CONTAGENS:
        celulas = [NOME[col]]
        for s in ("Masculino", "Feminino"):
            x = d[d["sexo"] == s][col]
            celulas.append(f"{fmt(x.mean())} ± {fmt(x.std())}")
        linhas.append(celulas)
    ritmo = d["n_ataque"] / 3
    dur_atq = (d["t_ataque"] / d["n_ataque"].replace(0, np.nan)).median()
    dur_def = (d["t_defesa"] / d["n_defesa"].replace(0, np.nan)).median()
    fig = fig_estados(df)
    texto = "\n".join([
        "## 2. Perfil médio por round", "",
        f"![Tempo por estado](figuras/e2/{fig})", "",
        "Tempo médio de cada estado v2.0 num round, por competição e sexo (M/F).", "",
        "Ciclo de Paris (Pan 2023 + Paris 2024), média ± desvio padrão por atleta × round:", "",
        tabela(["Variável", "Masculino", "Feminino"], linhas), "",
        f"- Ritmo de ataque: {fmt(ritmo.mean())} ações ofensivas por minuto "
        f"(DP {fmt(ritmo.std())}).",
        f"- Duração mediana por ação: ataque {fmt(dur_atq, 2)} s, defesa {fmt(dur_def, 2)} s "
        "(referência para as janelas da E5).",
        f"- Clinch é {fmt(100 * d['t_clinch'].sum() / d['t_pausa_v2'].sum(), 0)}% do tempo de pausa v2.0 "
        f"em Paris e {fmt(100 * df[df['ciclo'] == 'Tóquio']['t_clinch'].sum() / df[df['ciclo'] == 'Tóquio']['t_pausa_v2'].sum(), 0)}% "
        "no pré-olímpico 2020.",
    ])
    return texto, fig


def secao_rounds(df: pd.DataFrame) -> str:
    linhas, ps = [], []
    for col in TEMPOS + CONTAGENS:
        d = df.dropna(subset=[col])
        termos = "C(round) + C(sexo) + C(comp)"
        r = misto(f"{col} ~ {termos}", d)
        b2, b3 = r.params["C(round)[T.2]"], r.params["C(round)[T.3]"]
        p3 = r.pvalues["C(round)[T.3]"]
        m1 = d[d["round"] == 1][col].mean()
        linhas.append([NOME[col], fmt(m1), f"{'+' if b2 >= 0 else ''}{fmt(b2)}", f"{'+' if b3 >= 0 else ''}{fmt(b3)}"])
        ps.append(p3)
    for l, p in zip(linhas, holm(ps)):
        l.append(fmt_p(p))
    fig = fig_rounds(df)
    return "\n".join([
        "## 3. Efeito do round (cansaço / estratégia)", "",
        f"![Estados por round](figuras/e2/{fig})", "",
        "Modelo misto `variável ~ round + sexo + competição`, intercepto aleatório por luta. "
        "R2 e R3 são diferenças em relação ao R1, já descontados sexo e competição. Tempos usam as "
        "3 competições; contagens, só 2023–2024.", "",
        tabela(["Variável", "Média R1", "R2 − R1", "R3 − R1", "p (R3, Holm)"], linhas),
    ])


def secao_ciclos(df: pd.DataFrame) -> str:
    def estimar(dados: pd.DataFrame) -> list[list]:
        out = []
        for col in TEMPOS:
            r = misto(f"{col} ~ C(sexo, Treatment('Masculino')) * C(ciclo, Treatment('Tóquio')) + C(round)", dados)
            ef = "C(ciclo, Treatment('Tóquio'))[T.Paris]"
            sx = "C(sexo, Treatment('Masculino'))[T.Feminino]"
            it = f"{sx}:{ef}"
            out.append([col, r.params[ef], r.pvalues[ef], r.params[sx], r.pvalues[sx], r.params[it], r.pvalues[it]])
        return out

    def linhas_de(res: list[list]) -> list[list[str]]:
        pc, ps_, pi = (holm([r[i] for r in res]) for i in (2, 4, 6))
        sinal = lambda v: f"{'+' if v >= 0 else ''}{fmt(v)}"  # noqa: E731
        return [[NOME[r[0]], f"{sinal(r[1])} ({fmt_p(a)})", f"{sinal(r[3])} ({fmt_p(b)})",
                 f"{sinal(r[5])} ({fmt_p(c)})"] for r, a, b, c in zip(res, pc, ps_, pi)]

    medias = []
    for col in TEMPOS:
        cel = [NOME[col]]
        for ciclo in ("Tóquio", "Paris"):
            for s in ("Masculino", "Feminino"):
                cel.append(fmt(df[(df["ciclo"] == ciclo) & (df["sexo"] == s)][col].mean()))
        medias.append(cel)
    tudo = linhas_de(estimar(df))
    fases = df[df["fase"].isin(["Quartas", "Semifinal", "Final"])]
    so_fases = linhas_de(estimar(fases))
    cab = ["Variável", "Paris − Tóquio (homens)", "Fem. − Masc. (Tóquio)", "Interação sexo × ciclo"]
    return "\n".join([
        "## 4. Ciclos olímpicos × sexo (objetivo 3.2.3 da proposta)", "",
        "Médias por round (s):", "",
        tabela(["Variável", "Tóquio · M", "Tóquio · F", "Paris · M", "Paris · F"], medias), "",
        "Modelo misto `tempo ~ sexo × ciclo + round`, intercepto aleatório por luta. Cada célula: "
        "diferença em segundos (p corrigido por Holm entre as 6 variáveis). A interação diz se a "
        "diferença entre os ciclos é outra para as mulheres.", "",
        "**Todas as fases:**", "", tabela(cab, tudo), "",
        "**Só quartas, semifinais e finais** (as fases que existem nos dois ciclos):", "",
        tabela(cab, so_fases), "",
        "Cuidados: o ciclo de Tóquio é só a eliminatória europeia (não os Jogos), com outras "
        "categorias de peso e outro grupo de anotação possível; diferença de ciclo e de evento "
        "estão confundidas. Só tempos (2020 não tem contagens).",
    ])


def secao_resultado(df: pd.DataFrame) -> str:
    p = pares_cantos(df)
    p = p[p["vencedor_v"] != p["vencedor_a"]]
    linhas, ps = [], []
    for col in TEMPOS + CONTAGENS:
        venc = np.where(p["vencedor_v"] == 1, p[f"{col}_v"], p[f"{col}_a"])
        perd = np.where(p["vencedor_v"] == 1, p[f"{col}_a"], p[f"{col}_v"])
        ok = ~(np.isnan(venc) | np.isnan(perd))
        dif = venc[ok] - perd[ok]
        if len(dif) < 10:
            continue
        dz = dif.mean() / dif.std(ddof=1) if dif.std(ddof=1) > 0 else 0.0
        pv = stats.wilcoxon(dif).pvalue if np.any(dif != 0) else 1.0
        linhas.append([NOME[col], str(ok.sum()), fmt(venc[ok].mean()), fmt(perd[ok].mean()), fmt(dz, 2)])
        ps.append(pv)
    for l, pv in zip(linhas, holm(ps)):
        l.append(fmt_p(pv))
    return "\n".join([
        "## 5. Vencedor × perdedor", "",
        "Pares do mesmo round (os dois cantos anotados), todas as competições. dz = diferença média "
        "÷ desvio padrão das diferenças (efeito pareado); p de Wilcoxon com Holm.", "",
        tabela(["Variável", "Rounds", "Vencedor", "Perdedor", "dz", "p (Holm)"], linhas), "",
        "Vencedor = vencedor da LUTA (a base não traz o vencedor de cada round). Clinch e pausa "
        "servem de controle: são eventos dos dois atletas, então não deveriam diferir. Nenhuma "
        "variável de volume ou tempo separa vencedor de perdedor: no boxe olímpico os juízes "
        "pontuam qualidade e efetividade, que a planilha não mede (golpe certo × errado fica para a E8).",
    ])


def secao_confiabilidade(df: pd.DataFrame) -> tuple[str, dict]:
    p = pares_cantos(df)
    linhas, ref = [], {}
    for col in ("t_clinch", "t_pausa", "t_pausa_v2", "n_clinch", "n_pausa", "n_pausa_v2"):
        x, y = p[f"{col}_v"].to_numpy(float), p[f"{col}_a"].to_numpy(float)
        ok = ~(np.isnan(x) | np.isnan(y))
        x, y = x[ok], y[ok]
        dif = x - y
        ref[col] = float(np.abs(dif).mean())
        linhas.append([NOME[col], str(ok.sum()), fmt(np.abs(dif).mean()), fmt(np.median(np.abs(dif))),
                       fmt(dif.mean()), fmt(1.96 * dif.std(ddof=1)), fmt(icc_a1(x, y), 2)])
    fig = fig_bland_altman(p, "t_pausa_v2", "Pausa v2.0")
    texto = "\n".join([
        "## 6. Confiabilidade da anotação manual (piso de erro)", "",
        "Clinch e pausa acontecem para os dois atletas ao mesmo tempo: as linhas Vermelho e Azul "
        "do mesmo round deveriam ser iguais. A diferença entre elas mede o erro da própria "
        "anotação manual. É a referência de \"bom o suficiente\" para o automático (E5/E6) e "
        "responde às métricas de concordância da proposta (ICC, Bland–Altman).", "",
        tabela(["Variável", "Rounds", "|V − A| médio", "|V − A| mediano", "Viés V − A", "± LoA 95%", "ICC(A,1)"], linhas), "",
        f"![Bland–Altman pausa v2.0](figuras/e2/{fig})", "",
        "Leitura: ICC ≥ 0,75 é concordância boa, ≥ 0,90 excelente (Koo & Li, 2016). Para o "
        "ataque, a defesa e o deslocamento, que são de cada atleta, não há como medir isso na "
        "base: falta um segundo anotador no mesmo round (V2 do formulário).",
    ])
    return texto, ref


def secao_estilos(df: pd.DataFrame) -> str:
    d = df[(df["ciclo"] == "Paris")].copy()
    perfil = d.groupby(["luta_id", "cor"]).agg(
        atleta=("atleta", "first"), sexo=("sexo", "first"), vencedor=("vencedor", "first"),
        t_desl=("t_deslocamento", "mean"), t_atq=("t_ataque", "mean"), t_def=("t_defesa", "mean"),
        t_pau=("t_pausa_v2", "mean"), n_atq=("n_ataque", "mean"), n_def=("n_defesa", "mean"),
        n_desl=("n_deslocamento", "mean")).reset_index()
    perfil["atq_min"] = perfil["n_atq"] / 3
    perfil["def_min"] = perfil["n_def"] / 3
    perfil["dur_atq"] = perfil["t_atq"] / perfil["n_atq"].replace(0, np.nan)
    perfil["desl_min"] = perfil["n_desl"] / 3
    feats = {"t_atq": "% tempo em ataque", "t_def": "% tempo em defesa", "t_pau": "% tempo em pausa",
             "atq_min": "ataques/min", "def_min": "defesas/min", "dur_atq": "s por ação ofensiva",
             "desl_min": "trechos de desl./min"}
    perfil = perfil.dropna(subset=list(feats))
    X = perfil[list(feats)].to_numpy(float)
    z = (X - X.mean(axis=0)) / X.std(axis=0)
    silh = {}
    for k in range(2, 7):
        km = KMeans(k, n_init=20, random_state=0).fit(z)
        silh[k] = silhouette_score(z, km.labels_)
    k = max(silh, key=silh.get)
    km = KMeans(k, n_init=20, random_state=0).fit(z)
    perfil["estilo"] = km.labels_

    def nomear(c: np.ndarray) -> str:
        top = np.argsort(-np.abs(c))[:2]
        return " · ".join(f"{list(feats.values())[i]} {'alto' if c[i] > 0 else 'baixo'}" for i in top)

    linhas = []
    for e in range(k):
        g = perfil[perfil["estilo"] == e]
        c = km.cluster_centers_[e]
        linhas.append([f"{e + 1}", nomear(c), str(len(g)),
                       *[fmt(100 * g[f].mean() / 180) if f.startswith("t_") else fmt(g[f].mean(), 2 if f == "dur_atq" else 1)
                         for f in feats],
                       fmt(100 * g["vencedor"].mean(), 0) + "%", fmt(100 * (g["sexo"] == "Feminino").mean(), 0) + "%"])
    tab_venc = pd.crosstab(perfil["estilo"], perfil["vencedor"])
    qui = stats.chi2_contingency(tab_venc)
    return "\n".join([
        "## 7. Estilos (primeiro agrupamento)", "",
        "Perfil de cada atleta em cada luta (média dos rounds, ciclo de Paris), 7 medidas "
        "padronizadas, k-means. Silhueta por k: "
        + ", ".join(f"k={kk} {fmt(s, 2)}" for kk, s in silh.items()) + f" → k = {k}.", "",
        tabela(["Grupo", "Marca (maiores desvios)", "Perfis", *feats.values(), "Vitórias", "Mulheres"], linhas), "",
        f"Estilo × resultado: χ² = {fmt(qui[0], 2)}, p = {fmt_p(qui[1])}. "
        f"Silhueta {fmt(silh[k], 2)}"
        + (": até ~0,25 os grupos são fracos (os atletas formam um contínuo, não tipos separados). "
           "O perfil do lutador (E7) deve usar a posição do atleta em cada escala (percentil na "
           "base), não um rótulo de grupo." if silh[k] <= 0.3 else ": grupos razoavelmente separados."),
    ])


def main() -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    df = carregar()
    perfil, _ = secao_perfil(df)
    conf, ref = secao_confiabilidade(df)
    partes = [
        "# E2 — Estudo da base MHdS",
        "",
        "Gerado por `src/estudo_base.py` a partir de `data/referencia/rounds_2023_2024.csv` e "
        "`rounds_2020.csv` (anotação manual v1.0). Não editar à mão: rodar o script de novo.",
        "",
        secao_amostra(df), "", perfil, "", secao_rounds(df), "", secao_ciclos(df), "",
        secao_resultado(df), "", conf, "", secao_estilos(df), "",
    ]
    DOC.write_text("\n".join(partes), encoding="utf-8")
    print(f"→ {DOC}  (figuras em {FIG})")
    print("piso humano |V − A|:", {k: round(v, 1) for k, v in ref.items()})


if __name__ == "__main__":
    main()
