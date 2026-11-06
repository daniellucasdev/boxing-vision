"""Tipo de golpe: classificação automática (src/golpes.py) × golpes revisados (página /golpes).

Para cada luta de src/lutas.py com golpes.json, só golpes dentro dos rounds:
  - distribuição automática dos tipos por atleta e round (sempre, mesmo sem revisão);
  - com revisão (data/golpes_revisados/<luta>.json):
      * detector: dos golpes revisados, quantos eram golpe, finta ou "não é golpe" (precisão);
      * tipo: matriz de confusão automático × revisado, acerto e cobertura (% com tipo),
        acerto da trajetória (reto/cruzado/gancho, sem a mão) e da mão (frente/trás);
      * contagem por round (atleta × round com todos os golpes revisados): erro médio por tipo,
        contra "chutar" a proporção média dos tipos (de outra luta, se houver).
    A revisão parte dos golpes DETECTADOS: golpes que o detector perdeu não entram (a cobertura
    vem da anotação completa no modo juiz, P9).

Gera docs/avaliacao_golpes.md.

CLI:
  python src/avaliar_golpes.py
"""

from __future__ import annotations

import json
from collections import Counter

import numpy as np

import golpes as gm
import lutas
from base_mhds import REPO, carregar_base
from estudo_base import fmt, tabela

DOC = REPO / "docs" / "avaliacao_golpes.md"
TIPOS = [k for k, v in gm.ROTULOS.items() if v is not None]           # 6 tipos com mão
NAO_TIPO = ("finta", "nao_golpe", "incerto")
TRAJ = {"jab": "reto", "direto": "reto", "cruzado_frente": "cruzado", "cruzado_tras": "cruzado",
        "gancho_frente": "gancho", "gancho_tras": "gancho"}
NOME = {"jab": "Jab", "direto": "Direto", "cruzado_frente": "Cruzado frente", "cruzado_tras": "Cruzado trás",
        "gancho_frente": "Gancho frente", "gancho_tras": "Gancho trás", None: "Sem tipo",
        "finta": "Finta", "nao_golpe": "Não é golpe", "incerto": "Não dá para ver"}


def carregar() -> list[dict]:
    """Golpes dentro dos rounds, com luta, round, atleta, rótulo automático e revisado."""
    base = carregar_base()
    linhas = []
    for luta in lutas.LUTAS:
        pasta = REPO / lutas.pasta(luta)
        if not (pasta / "golpes.json").exists():
            continue
        fps = float(np.load(pasta / "serie.npz")["fps"])
        atletas = {r["cor"]: r["atleta"] for r in base if str(r["luta_id"]) == luta["luta_id"]}
        rev = gm.ler_revisao(luta["nome"])["rotulos"]
        for g in json.loads((pasta / "golpes.json").read_text())["golpes"]:
            rnd = lutas.round_de(luta, (int(g["frame"]) - 1) / fps)
            if rnd is None:
                continue
            linhas.append({"luta": luta["nome"], "luta_id": luta["luta_id"], "round": rnd, "cor": g["boxer"],
                           "atleta": atletas.get(g["boxer"], g["boxer"]), "auto": gm.rotulo_auto(g),
                           "rev": (rev.get(gm.golpe_id(g)) or {}).get("rotulo")})
    return linhas


def pct(a: int, b: int) -> str:
    return f"{100 * a / b:.0f}%" if b else "—"


def secao_distribuicao(linhas: list[dict]) -> list[str]:
    linhas_tab = []
    for (lid, atleta), gs in _agrupar(linhas, ("luta_id", "atleta")).items():
        c = Counter(g["auto"] for g in gs)
        n = len(gs)
        linhas_tab.append([lid, atleta, str(n), *[pct(c[t], n) for t in (*TIPOS, None)]])
    return ["## 1. Distribuição automática (sem revisão)", "",
            "Golpes detectados dentro dos 3 rounds, por atleta. Percentual de cada tipo atribuído pelas regras.", "",
            tabela(["luta_id", "Atleta", "Golpes", *[NOME[t] for t in (*TIPOS, None)]], linhas_tab), "",
            "Sanidade esperada no boxe olímpico: jab e direto como golpes mais frequentes. Muito \"sem tipo\" "
            "indica pose insuficiente (close, oclusão, golpe na direção da câmera) ou guarda indefinida.", ""]


def _agrupar(linhas, chaves):
    out: dict = {}
    for l in linhas:
        out.setdefault(tuple(l[k] for k in chaves), []).append(l)
    return dict(sorted(out.items()))


def secao_revisao(linhas: list[dict]) -> list[str]:
    rev = [l for l in linhas if l["rev"]]
    if not rev:
        return ["## 2. Contra a revisão", "",
                "Nenhum golpe revisado ainda. Abra a página **Golpes** da interface web "
                "(`python src/webapp.py` → /golpes) e revise pelo menos 1 round inteiro de cada luta "
                "(~7 min por round). Depois rode este script de novo.", ""]
    out = ["## 2. Contra a revisão", ""]
    # detector
    c = Counter(l["rev"] for l in rev)
    tipados = sum(c[t] for t in TIPOS)
    validos = len(rev) - c["incerto"]
    out += ["### 2.1 Detector de golpes", "",
            tabela(["Revisados", "Golpe tipado", "Finta", "Não é golpe", "Não dá para ver", "Precisão (golpe ou finta)"],
                   [[str(len(rev)), str(tipados), str(c["finta"]), str(c["nao_golpe"]), str(c["incerto"]),
                     pct(tipados + c["finta"], validos)]]), ""]
    # tipo
    t = [l for l in rev if l["rev"] in TIPOS]
    com = [l for l in t if l["auto"]]
    acerto = sum(l["auto"] == l["rev"] for l in com)
    traj = sum(TRAJ[l["auto"]] == TRAJ[l["rev"]] for l in com)
    mao = sum(gm.ROTULOS[l["auto"]][1] == gm.ROTULOS[l["rev"]][1] for l in com)
    out += ["### 2.2 Tipo de golpe", "",
            f"{len(t)} golpes revisados com tipo; {len(com)} ({pct(len(com), len(t))}) receberam tipo automático.", "",
            tabela(["Acerto do tipo (com mão)", "Acerto da trajetória (reto/cruzado/gancho)", "Acerto da mão",
                    "Cobertura (com tipo)"],
                   [[pct(acerto, len(com)), pct(traj, len(com)), pct(mao, len(com)), pct(len(com), len(t))]]), "",
            "Matriz de confusão (linhas = revisão, colunas = automático):", ""]
    cols = [*TIPOS, None]
    mat = [[NOME[r], *[str(sum(1 for l in t if l["rev"] == r and l["auto"] == a)) for a in cols],
            pct(sum(1 for l in t if l["rev"] == r and l["auto"] == r), sum(1 for l in t if l["rev"] == r))]
           for r in TIPOS]
    out += [tabela(["Revisão \\ auto", *[NOME[a] for a in cols], "Acerto (sensibilidade)"], mat), ""]
    out += secao_contagem(linhas)
    return out


def secao_contagem(linhas: list[dict]) -> list[str]:
    grupos = {k: gs for k, gs in _agrupar(linhas, ("luta", "luta_id", "round", "atleta")).items()
              if all(g["rev"] for g in gs)}
    if not grupos:
        return ["### 2.3 Contagem por round", "",
                "Nenhum atleta × round com todos os golpes revisados ainda; o erro por round sai quando houver.", ""]
    erros = {t: [] for t in TIPOS}
    chute = {t: [] for t in TIPOS}
    por_linha = []
    todas = [l for l in linhas if l["rev"] in TIPOS]
    for (luta, lid, rnd, atleta), gs in grupos.items():
        outras = [l for l in todas if l["luta"] != luta] or todas  # proporção de outra luta, se houver
        prop = {t: sum(l["rev"] == t for l in outras) / max(len(outras), 1) for t in TIPOS}
        n_auto = len(gs)
        linha = [lid, str(rnd), atleta]
        for t in TIPOS:
            a = sum(g["auto"] == t for g in gs)
            r = sum(g["rev"] == t for g in gs)
            erros[t].append(abs(a - r))
            chute[t].append(abs(n_auto * prop[t] - r))
            linha.append(f"{a} / {r}")
        por_linha.append(linha)
    met = [[NOME[t], fmt(np.mean(erros[t])), fmt(np.mean(chute[t]))] for t in TIPOS]
    return ["### 2.3 Contagem por round", "",
            f"{len(grupos)} atleta × round com todos os golpes revisados. Erro médio absoluto da contagem de cada "
            "tipo; \"chute\" = golpes detectados × proporção média do tipo na revisão (de outra luta, quando há).", "",
            tabela(["Tipo", "Erro médio automático", "Erro médio do chute"], met), "",
            "Linha a linha (automático / revisado):", "",
            tabela(["luta_id", "Round", "Atleta", *[NOME[t] for t in TIPOS]], por_linha), ""]


def main() -> None:
    linhas = carregar()
    if not linhas:
        raise SystemExit("nenhuma luta com golpes.json: rode src/golpes.py nas lutas de src/lutas.py")
    lids = sorted({l["luta_id"] for l in linhas})
    doc = ["# Tipo de golpe — automático × revisão", "",
           "Gerado por `src/avaliar_golpes.py`. Não editar à mão: rodar o script de novo.", "",
           f"{len(linhas)} golpes detectados dentro dos rounds, {len(lids)} lutas (luta_id {', '.join(lids)}); "
           f"{sum(1 for l in linhas if l['rev'])} revisados.", "",
           "Tipos: jab (reto da mão da frente), direto (reto da mão de trás), cruzado (hook) e gancho "
           "(uppercut) da mão da frente ou de trás. A base MHdS não registra tipo de golpe: o gabarito é a "
           "revisão feita na página /golpes.", "",
           *secao_distribuicao(linhas), *secao_revisao(linhas)]
    DOC.write_text("\n".join(doc), encoding="utf-8")
    print(f"{len(linhas)} golpes ({sum(1 for l in linhas if l['rev'])} revisados) → {DOC}")


if __name__ == "__main__":
    main()
