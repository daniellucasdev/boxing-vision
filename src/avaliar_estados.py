"""E5 — avaliação dos estados automáticos contra a base MHdS (anotação manual v1.0).

Para cada luta já processada pelo pipeline (eventos.json, serie.npz, deslocamento.csv), gera as
marcas da E5 (estados.anotar), resume no layout da planilha (anotacao.resumir) e compara linha a
linha (atleta × round) com a base. Métricas por variável, as que a proposta deve usar:

  - erro médio absoluto (MAE) e o MAE de "chutar a média da base" em toda linha (referência);
  - Bland–Altman: viés (automático − manual) e limites de concordância de 95%;
  - ICC(A,1) (concordância absoluta) e correlação de Pearson;
  - piso humano: na própria base, a pausa do mesmo round difere entre os dois cantos (seção 6 de
    docs/estudo_base.md); o automático não tem como ficar muito abaixo disso.

Gera docs/avaliacao_e5.md. Para incluir uma luta nova, acrescente-a em src/lutas.py (ou use --luta).

CLI:
  python src/avaliar_estados.py
  python src/avaliar_estados.py --luta outputs/lutas/x:94:49,289.17,529.33
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

import anotacao
import estados
import lutas
from base_mhds import REPO, carregar_base
from estudo_base import fmt, icc_a1, tabela

DOC = REPO / "docs" / "avaliacao_e5.md"

# pasta de saída do pipeline, luta_id na base, início de cada round no vídeo (lista em src/lutas.py)
LUTAS = [(lutas.pasta(l), l["luta_id"], l["inicios"]) for l in lutas.LUTAS]
CAMPOS = [(f"{p}_{e}", f"{p}_{e}" + ("_v2" if e == "pausa" else "")) for p in ("t", "n") for e in anotacao.ESTADOS]


def comparar(lutas) -> list[dict]:
    base = carregar_base()
    linhas = []
    for pasta, luta_id, inicios in lutas:
        base_luta = [r for r in base if str(r["luta_id"]) == str(luta_id)]
        for doc in estados.anotar(REPO / pasta, inicios, base_luta=base_luta):
            m = doc["meta"]
            b = next((r for r in base_luta if r["cor"] == m["cor"] and str(r["round"]) == m["round"]), None)
            if b is None:
                continue
            linhas.append({"luta": Path(pasta).name, "luta_id": luta_id, "round": m["round"], "cor": m["cor"],
                           "atleta": m["atleta"], "auto": anotacao.resumir(anotacao.validar(doc)), "base": b})
    return linhas


def relatorio(linhas: list[dict]) -> str:
    base = carregar_base()
    media = {b: float(np.mean([r[b] for r in base])) for _, b in CAMPOS}
    met = []
    for a, b in CAMPOS:
        x = np.array([l["auto"][a] for l in linhas], float)
        y = np.array([l["base"][b] for l in linhas], float)
        d = x - y
        r = np.corrcoef(x, y)[0, 1] if x.std() > 0 and y.std() > 0 else float("nan")
        met.append([a.replace("_", " ", 1), fmt(x.mean()), fmt(y.mean()), fmt(np.abs(d).mean()),
                    fmt(np.abs(media[b] - y).mean()), fmt(d.mean()), fmt(1.96 * d.std(ddof=1)),
                    fmt(icc_a1(x, y), 2), fmt(r, 2)])
    por_linha = [[l["luta_id"], l["round"], l["cor"], l["atleta"] or "—",
                  *[f"{l['auto'][a]:.0f} / {l['base'][b]:.0f}" for a, b in CAMPOS[:4]]] for l in linhas]
    lutas = sorted({l["luta_id"] for l in linhas})
    return "\n".join([
        "# E5 — Estados automáticos × base MHdS", "",
        "Gerado por `src/avaliar_estados.py`. Não editar à mão: rodar o script de novo.", "",
        f"{len(linhas)} linhas (atleta × round) de {len(lutas)} lutas (luta_id {', '.join(lutas)}).", "",
        "## Métricas por variável", "",
        tabela(["Variável", "Média auto", "Média base", "MAE", "MAE chutando a média", "Viés (auto − base)",
                "± LoA 95%", "ICC(A,1)", "r"], met), "",
        "Piso humano (docs/estudo_base.md, seção 6): a pausa v2.0 do mesmo round difere em média "
        "5,0 s entre os dois cantos (ICC 0,91). O automático é útil quando o MAE fica perto disso "
        "e abaixo do MAE de chutar a média.", "",
        "Com poucas lutas o ICC e o r são instáveis (cada luta tem só 6 linhas, e as 2 do mesmo "
        "round compartilham a pausa). Leia o MAE primeiro.", "",
        "## Linha a linha (automático / base, segundos)", "",
        tabela(["luta_id", "Round", "Canto", "Atleta", "Deslocamento", "Ataque", "Defesa", "Pausa"], por_linha), "",
    ])


def main() -> None:
    ap = argparse.ArgumentParser(description="E5: estados automáticos × base MHdS → docs/avaliacao_e5.md")
    ap.add_argument("--luta", action="append", default=[],
                    help="pasta:luta_id:inicio1,inicio2,inicio3 (substitui a lista padrão)")
    args = ap.parse_args()
    lutas = [(p, i, [float(s) for s in ini.split(",")]) for p, i, ini in (l.rsplit(":", 2) for l in args.luta)] \
        if args.luta else LUTAS
    faltando = [p for p, _, _ in lutas if not (REPO / p / "serie.npz").exists()]
    if faltando:
        raise SystemExit(f"rode o pipeline antes (src/features.py --save) em: {', '.join(faltando)}")
    linhas = comparar(lutas)
    DOC.write_text(relatorio(linhas), encoding="utf-8")
    print(f"{len(linhas)} linhas → {DOC}")


if __name__ == "__main__":
    main()
