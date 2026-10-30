"""E0 — base de referência MHdS (v1.0, anotação manual) convertida em CSV.

Lê a aba "Olimpico e Pre-2024" da planilha original só com a biblioteca padrão
(xlsx = zip de XMLs), normaliza grafias e acrescenta as colunas da v2.0, em que
o clinch passa a contar como pausa:
    t_pausa_v2 = t_clinch + t_pausa      n_pausa_v2 = n_clinch + n_pausa

Normalizações: espaços extras; Vermleho → Vermelho; Vencedo/Ganhador → Vencedor;
fases (R32, Oitavas, Quartas, Semifinal, Final); categorias sem "Peso" e sem a
faixa de kg entre parênteses, com o código da aba "Códigos" (numeração por sexo).
t_total é recalculado como a soma dos 5 tempos.

CLI:
  python src/base_mhds.py --xlsx "data/referencia/Análises MHdS 2026-atual.xlsx"
  → data/referencia/rounds_2023_2024.csv

Programático (usado pelo modo juiz para comparar com a base):
  from base_mhds import carregar_base
  linhas = carregar_base()
"""

from __future__ import annotations

import argparse
import csv
import re
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CSV_PADRAO = REPO / "data" / "referencia" / "rounds_2023_2024.csv"
ABA = "Olimpico e Pre-2024"

_NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}

# colunas da aba (o cabeçalho repete "Deslocamento"... para tempo e contagem → mapear por letra)
_COLUNAS = {
    "A": "round", "B": "pais", "C": "atleta", "D": "cor", "E": "sexo", "F": "categoria",
    "G": "competicao", "H": "fase", "I": "resultado", "J": "pais_oponente", "K": "oponente",
    "L": "t_deslocamento", "M": "t_ataque", "N": "t_defesa", "O": "t_clinch", "P": "t_pausa",
    "Q": "t_total_planilha",
    "R": "n_deslocamento", "S": "n_ataque", "T": "n_defesa", "U": "n_clinch", "V": "n_pausa",
}
TEMPOS = ("t_deslocamento", "t_ataque", "t_defesa", "t_clinch", "t_pausa")
CONTAGENS = ("n_deslocamento", "n_ataque", "n_defesa", "n_clinch", "n_pausa")

CAMPOS_CSV = [
    "luta_id", "round", "atleta", "pais", "cor", "sexo", "categoria_cod", "categoria",
    "competicao", "fase", "resultado", "oponente", "pais_oponente",
    *TEMPOS, "t_total", *CONTAGENS, "t_pausa_v2", "n_pausa_v2", "fonte",
]

_FASES = {
    "round of 32": "R32",
    "oitavas de final": "Oitavas", "oitavas de finais": "Oitavas",
    "quartas de final": "Quartas", "quartas de finais": "Quartas",
    "semi-final": "Semifinal", "semi-finais": "Semifinal",
    "final": "Final", "finais": "Final",
}
_CATEGORIAS = {
    "Masculino": ["Ligeiro", "Super Mosca", "Galo", "Super Galo", "Super Pena", "Leve",
                  "Super Leve", "Médio", "Cruzador", "Pesado"],
    "Feminino": ["Mosca", "Super Galo", "Pena", "Super Pena", "Leve", "Médio",
                 "Super Médio", "Pesado"],
}


def sem_acento(s: str) -> str:
    """Chave de busca: minúsculas, sem acentos (usada também pela busca do modo juiz)."""
    return "".join(c for c in unicodedata.normalize("NFD", s.lower())
                   if unicodedata.category(c) != "Mn")


def _limpa(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _categoria(bruta: str) -> str:
    s = re.sub(r"\(.*?\)", "", bruta)          # "Peso Leve (60 a 62Kg)" → "Peso Leve"
    s = re.sub(r"^Peso\s+", "", _limpa(s))
    return _limpa(s)


def _linhas_xlsx(caminho: Path, aba: str) -> list[dict[str, str]]:
    with zipfile.ZipFile(caminho) as z:
        compart = []
        if "xl/sharedStrings.xml" in z.namelist():
            raiz = ET.fromstring(z.read("xl/sharedStrings.xml"))
            compart = ["".join(t.text or "" for t in si.iter(f"{{{_NS['m']}}}t"))
                       for si in raiz.findall("m:si", _NS)]
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rid = next((s.get(f"{{{_NS['r']}}}id") for s in wb.iter(f"{{{_NS['m']}}}sheet")
                    if s.get("name") == aba), None)
        if rid is None:
            raise ValueError(f"aba '{aba}' não encontrada em {caminho.name}")
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        alvo = next(r.get("Target") for r in rels.findall("rel:Relationship", _NS)
                    if r.get("Id") == rid)
        planilha = ET.fromstring(z.read("xl/" + alvo.lstrip("/").removeprefix("xl/")))

    linhas = []
    for row in planilha.iter(f"{{{_NS['m']}}}row"):
        valores = {}
        for c in row.findall("m:c", _NS):
            letra = re.sub(r"\d", "", c.get("r", ""))
            v = c.find("m:v", _NS)
            if v is None or v.text is None:
                continue
            valores[letra] = compart[int(v.text)] if c.get("t") == "s" else v.text
        linhas.append(valores)
    return linhas


def converter(xlsx: Path) -> tuple[list[dict], int]:
    """Lê a planilha e devolve (linhas limpas, nº de linhas descartadas por falta de número)."""
    brutas = _linhas_xlsx(xlsx, ABA)[1:]  # 1ª linha = cabeçalho
    linhas, descartadas = [], 0
    lutas: dict[tuple, int] = {}
    for b in brutas:
        r = {campo: _limpa(b.get(letra, "")) for letra, campo in _COLUNAS.items()}
        try:
            for campo in ("round", *TEMPOS, *CONTAGENS):
                r[campo] = float(r[campo])
        except ValueError:
            descartadas += 1
            continue
        r["round"] = int(r["round"])
        for campo in CONTAGENS:
            r[campo] = int(round(r[campo]))
        for campo in TEMPOS:
            r[campo] = round(r[campo], 2)

        r["cor"] = {"Vermleho": "Vermelho"}.get(r["cor"], r["cor"])
        r["resultado"] = {"Vencedo": "Vencedor", "Ganhador": "Vencedor"}.get(
            r["resultado"], r["resultado"])
        r["fase"] = _FASES.get(r["fase"].lower(), r["fase"])
        r["categoria"] = _categoria(r["categoria"])
        nomes = _CATEGORIAS.get(r["sexo"], [])
        r["categoria_cod"] = nomes.index(r["categoria"]) + 1 if r["categoria"] in nomes else ""

        r["t_total"] = round(sum(r[c] for c in TEMPOS), 2)
        r["t_pausa_v2"] = round(r["t_clinch"] + r["t_pausa"], 2)
        r["n_pausa_v2"] = r["n_clinch"] + r["n_pausa"]
        # luta = competição + fase + categoria + par de nomes (heurístico: grafias diferentes quebram)
        chave = (r["competicao"], r["fase"], r["categoria"],
                 tuple(sorted((sem_acento(r["atleta"]), sem_acento(r["oponente"])))))
        r["luta_id"] = lutas.setdefault(chave, len(lutas) + 1)
        r["fonte"] = ABA
        linhas.append({k: r[k] for k in CAMPOS_CSV})
    return linhas, descartadas


def chave_base(linha: dict) -> str:
    """Identifica 1 linha da base (atleta × round × luta) para o modo juiz guardar a referência."""
    return f"{linha['competicao']}|{linha['fase']}|{linha['atleta']}|{linha['oponente']}|{linha['round']}"


_cache: dict = {"mtime": None, "linhas": []}


def carregar_base(caminho: Path = CSV_PADRAO) -> list[dict]:
    """Linhas do CSV com números convertidos; [] se a base ainda não foi gerada."""
    if not caminho.exists():
        return []
    mtime = caminho.stat().st_mtime
    if _cache["mtime"] != mtime:
        with open(caminho, newline="", encoding="utf-8") as f:
            linhas = list(csv.DictReader(f))
        for r in linhas:
            for campo in (*TEMPOS, "t_total", "t_pausa_v2"):
                r[campo] = float(r[campo])
            for campo in ("round", "luta_id", *CONTAGENS, "n_pausa_v2"):
                r[campo] = int(r[campo])
            r["chave"] = chave_base(r)
        _cache.update(mtime=mtime, linhas=linhas)
    return _cache["linhas"]


def main() -> None:
    ap = argparse.ArgumentParser(description="E0: planilha MHdS (xlsx) → CSV limpo com colunas v2.0")
    ap.add_argument("--xlsx", required=True, help="planilha 'Análises MHdS' original")
    ap.add_argument("--out", default=str(CSV_PADRAO))
    args = ap.parse_args()

    linhas, descartadas = converter(Path(args.xlsx))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS_CSV)
        w.writeheader()
        w.writerows(linhas)

    sem_cod = sorted({(r["sexo"], r["categoria"]) for r in linhas if r["categoria_cod"] == ""})
    fora = [r for r in linhas if not 175 <= r["t_total"] <= 185]
    print(f"{len(linhas)} rounds → {out}  ({descartadas} linhas sem números descartadas)")
    print(f"lutas (luta_id heurístico): {len({r['luta_id'] for r in linhas})}")
    print(f"rounds com t_total fora de 175–185 s: {len(fora)}")
    if sem_cod:
        print(f"categorias sem código: {sem_cod}")


if __name__ == "__main__":
    main()
