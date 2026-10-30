"""E5 — os 4 estados da planilha por regras: pré-anotação automática no formato do modo juiz.

Em vez de calcular a planilha direto, o software escreve as MESMAS marcas que o juiz
escreveria no modo juiz (troca de estado + ações pontuais). Assim a contagem, os CSVs e a
comparação com a base são os de anotacao.py, e o juiz pode abrir a pré-anotação no modo
juiz e só corrigir.

Regras por quadro, com a prioridade da v1.0: Pausa > Ataque > Defesa > Deslocamento.

  - Pausa (igual para os dois atletas):
      clinch = pés dos dois a menos de CLINCH_DIST corpos no chão (escorço da E4); sem os
               pés (close), caixas dos dois sobrepostas em ≥ CLINCH_SOBREPOSICAO da menor;
      luta parada = árbitro ENTRE os atletas (separando, advertindo, contando).
    Lacunas curtas são preenchidas e pausas curtas descartadas.
  - Ataque: trecho de ATAQUE_ANTES + ATAQUE_DEPOIS em volta de cada golpe detectado;
    golpes próximos formam uma sequência. Cada golpe vira a ação "golpe" (o detector não
    separa golpe de finta).
  - Defesa: golpe do OPONENTE dirigido ao atleta (punho a menos de DEFESA_ALCANCE larguras
    de ombro do nariz: só descarta golpe no vazio, de longe), fora do próprio ataque → trecho de defesa
    e ação "defesa" sem subtipo (bloqueio/esquiva/guarda não são distinguidos).
  - Deslocamento: o resto, com a direção da E4 quando os pés estão no quadro.

A duração por ação vem da base MHdS: 31,3 s de ataque para 68,6 ações e 13,3 s de defesa
para 28,9 ações por round (~0,46 s por ação nos dois casos).
"""

from __future__ import annotations

import warnings

import numpy as np

from deslocamento import ESCORCO

CLINCH_DIST = 0.45       # corpos, entre os pés dos dois atletas no chão
CLINCH_MIN_S = 0.8
CLINCH_SOBREPOSICAO = 0.45  # interseção / caixa menor; mediana 0,44–0,51 com sep < 0,45 e ~0 com sep > 0,7
ARBITRO_ENTRE = (0.15, 0.85)  # projeção do árbitro no segmento atleta→atleta
ARBITRO_LARGURA = 0.6    # corpos: distância máxima do árbitro à linha entre os atletas
ARBITRO_MAX_SEP = 3.0    # corpos: atletas mais longe que isso não estão "sendo separados"
PAUSA_MIN_S = 1.0
PAUSA_LACUNA_S = 0.6     # buracos menores que isso dentro da pausa são preenchidos
DESCONHECIDO_MAX_S = 8.0 # sem os dois atletas no quadro: mantém a pausa se ela continua depois
ATAQUE_ANTES, ATAQUE_DEPOIS = 0.25, 0.25
ATAQUE_LACUNA_S = 0.35   # golpes mais próximos que isso = mesma sequência
DEFESA_ALCANCE = 10.0    # larguras de ombro do punho do oponente até o nariz (só descarta golpe no vazio, de longe)
DEFESA_ANTES, DEFESA_DEPOIS = 0.2, 0.3
DESL_MIN_S = 0.2         # deslocamento mais curto que isso entre duas ações não é trecho


def _corridas(mask: np.ndarray) -> list[tuple[int, int]]:
    """[(ini, fim_exclusivo)] dos trechos True."""
    m = np.concatenate([[False], mask.astype(bool), [False]])
    d = np.flatnonzero(np.diff(m.astype(np.int8)))
    return list(zip(d[::2], d[1::2]))


def _limpar(mask: np.ndarray, lacuna: int, minimo: int) -> np.ndarray:
    """Preenche buracos < lacuna e descarta trechos < minimo (em quadros)."""
    out = mask.copy()
    for a, b in _corridas(~out):
        if a > 0 and b < len(out) and b - a < lacuna:
            out[a:b] = True
    for a, b in _corridas(out):
        if b - a < minimo:
            out[a:b] = False
    return out


def _chao(p: np.ndarray) -> np.ndarray:
    """Coordenadas da tela → chão (vertical dividido pelo escorço)."""
    return np.stack([p[..., 0], p[..., 1] / ESCORCO], axis=-1)


def sobreposicao(caixas: np.ndarray) -> np.ndarray:
    """(N, 2, 4) xyxy → interseção / área da caixa menor por quadro (NaN se faltar uma)."""
    b0, b1 = caixas[:, 0], caixas[:, 1]
    ix = np.clip(np.minimum(b0[:, 2], b1[:, 2]) - np.maximum(b0[:, 0], b1[:, 0]), 0, None)
    iy = np.clip(np.minimum(b0[:, 3], b1[:, 3]) - np.maximum(b0[:, 1], b1[:, 1]), 0, None)
    area = np.minimum((b0[:, 2] - b0[:, 0]) * (b0[:, 3] - b0[:, 1]), (b1[:, 2] - b1[:, 0]) * (b1[:, 3] - b1[:, 1]))
    return ix * iy / np.maximum(area, 1.0)


def pausa(pes: np.ndarray, altura: np.ndarray, arbitro: np.ndarray, fps: float,
          caixas: np.ndarray | None = None) -> tuple[np.ndarray, dict]:
    """Máscara de pausa por quadro (clinch ou árbitro entre os atletas).

    pes: (N, 2, 2) pés (reais ou estimados) de Vermelho e Azul; altura: (N, 2) corpo em px;
    arbitro: (N, 2) pés do árbitro; caixas: (N, 2, 4) dos atletas (opcional, clinch em close).
    NaN = ausente.
    """
    n = len(pes)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # quadros sem nenhum atleta
        corpo = np.nanmean(altura, axis=1)
    v, a = _chao(pes[:, 0]), _chao(pes[:, 1])
    sep = np.linalg.norm(a - v, axis=1) / corpo
    conhecido = np.isfinite(sep)
    clinch = conhecido & (sep < CLINCH_DIST)
    if caixas is not None:
        sob = sobreposicao(caixas)
        close = ~conhecido & np.isfinite(sob)
        clinch |= close & (sob >= CLINCH_SOBREPOSICAO)
        conhecido = conhecido | close

    r = _chao(arbitro)
    eixo = a - v
    comp2 = np.maximum((eixo ** 2).sum(axis=1), 1e-6)
    proj = ((r - v) * eixo).sum(axis=1) / comp2
    perp = np.abs(eixo[:, 0] * (r - v)[:, 1] - eixo[:, 1] * (r - v)[:, 0]) / np.sqrt(comp2) / corpo
    entre = (conhecido & np.isfinite(proj) & (proj > ARBITRO_ENTRE[0]) & (proj < ARBITRO_ENTRE[1])
             & (perp < ARBITRO_LARGURA) & (sep < ARBITRO_MAX_SEP))

    bruto = clinch | entre
    clinch = _limpar(clinch, round(PAUSA_LACUNA_S * fps), round(CLINCH_MIN_S * fps))
    bruto = _limpar(bruto | clinch, round(PAUSA_LACUNA_S * fps), 1)
    # sem os dois atletas (close no corner, plano do árbitro): mantém a pausa se ela segue depois
    for i, j in _corridas(~conhecido):
        if 0 < i and j < n and bruto[i - 1] and bruto[j] and j - i <= DESCONHECIDO_MAX_S * fps:
            bruto[i:j] = True
    final = _limpar(bruto, round(PAUSA_LACUNA_S * fps), round(PAUSA_MIN_S * fps))
    diag = {"clinch_pct": round(100 * clinch.mean(), 1), "arbitro_entre_pct": round(100 * entre.mean(), 1),
            "conhecido_pct": round(100 * conhecido.mean(), 1), "separacao_mediana": round(float(np.nanmedian(sep)), 2)
            if conhecido.any() else None}
    return final, diag


def _trechos_acao(quadros: list[int], n: int, antes: int, depois: int, lacuna: int) -> np.ndarray:
    m = np.zeros(n, bool)
    for f in quadros:
        m[max(0, f - antes):min(n, f + depois + 1)] = True
    return _limpar(m, lacuna, 1)


def estados_por_quadro(n: int, fps: float, pausa_mask: np.ndarray, golpes: list[list[int]],
                       defesas: list[list[int]]) -> np.ndarray:
    """(2, N) com 0 deslocamento, 1 ataque, 2 defesa, 3 pausa."""
    out = np.zeros((2, n), np.int8)
    for k in range(2):
        atq = _trechos_acao(golpes[k], n, round(ATAQUE_ANTES * fps), round(ATAQUE_DEPOIS * fps),
                            round(ATAQUE_LACUNA_S * fps))
        dfs = _trechos_acao(defesas[k], n, round(DEFESA_ANTES * fps), round(DEFESA_DEPOIS * fps),
                            round(ATAQUE_LACUNA_S * fps))
        e = np.zeros(n, np.int8)
        e[dfs] = 2
        e[atq] = 1
        # deslocamento curto espremido entre duas ações: o juiz não marcaria
        for a, b in _corridas(e == 0):
            if 0 < a and b < n and b - a < DESL_MIN_S * fps:
                e[a:b] = e[a - 1]
        e[pausa_mask] = 3
        out[k] = e
    return out


def defesas_por_golpes(eventos: list[dict], cores=("Vermelho", "Azul")) -> list[list[int]]:
    """Golpes do oponente dirigidos ao atleta → defesas de cada atleta."""
    out: list[list[int]] = [[], []]
    for e in eventos:
        d = e.get("dist_cabeca_opp")
        if d is not None and d != "" and float(d) <= DEFESA_ALCANCE:
            out[1 - cores.index(e["boxer"])].append(int(e["frame"]) - 1)
    return out


NOMES = ("deslocamento", "ataque", "defesa", "pausa")
CORES = ("Vermelho", "Azul")


def marcas_round(estados: np.ndarray, direcao: list[str | None], golpes: list[int], defesas: list[int],
                 fps: float, ini: int, fim: int) -> list[dict]:
    """Marcas do modo juiz para 1 atleta entre os quadros [ini, fim) (índices 0-based)."""
    marcas = []
    ant = None
    for f in range(ini, fim):
        est = NOMES[estados[f]]
        d = direcao[f] if est == "deslocamento" else None
        if (est, d) != ant:
            marcas.append({"t": round(f / fps, 3), "tipo": "estado", "estado": est, "dir": d})
            ant = (est, d)
    marcas.append({"t": round(fim / fps, 3), "tipo": "estado", "estado": "fim", "dir": None})
    for f in golpes:
        if ini <= f < fim and estados[f] == 1:
            marcas.append({"t": round(f / fps, 3), "tipo": "acao", "acao": "golpe"})
    for f in defesas:
        if ini <= f < fim and estados[f] == 2:
            marcas.append({"t": round(f / fps, 3), "tipo": "acao", "acao": "defesa"})
    return sorted(marcas, key=lambda m: (m["t"], m["tipo"] != "estado"))


def anotar(out_dir, inicios_s: list[float], video: str = "", base_luta: list[dict] | None = None,
           duracao_s: float = 180.0) -> list[dict]:
    """Saída do pipeline (eventos.json, serie.npz, deslocamento.csv) → 1 doc do modo juiz
    por atleta × round. base_luta: linhas da base MHdS dessa luta (preenche o cabeçalho e
    liga a comparação)."""
    import csv
    import json
    from pathlib import Path

    out_dir = Path(out_dir)
    z = np.load(out_dir / "serie.npz")
    fps = float(z["fps"])
    n = len(z["pes"])
    eventos = json.loads((out_dir / "eventos.json").read_text())["eventos"]
    direcao: list[list[str | None]] = [[None] * n, [None] * n]
    with open(out_dir / "deslocamento.csv", newline="") as f:
        for r in csv.DictReader(f):
            if r.get("rotulo") in ("frente", "tras", "esq", "dir") and int(r["frame"]) <= n:
                direcao[CORES.index(r["slot"])][int(r["frame"]) - 1] = r["rotulo"]

    pm, _ = pausa(z["pes"], z["altura"], z["arbitro"], fps, z["caixa"] if "caixa" in z else None)
    golpes = [[int(e["frame"]) - 1 for e in eventos if e["boxer"] == c] for c in CORES]
    defesas = defesas_por_golpes(eventos)
    est = estados_por_quadro(n, fps, pm, golpes, defesas)
    docs = []
    for ri, ini_s in enumerate(inicios_s, start=1):
        ini, fim = round(ini_s * fps), min(n, round((ini_s + duracao_s) * fps))
        for k, cor in enumerate(CORES):
            b = next((r for r in base_luta or [] if r["cor"] == cor and str(r["round"]) == str(ri)), None)
            meta = {c: str((b or {}).get(c, "")) for c in ("atleta", "pais", "cor", "sexo", "categoria",
                                                      "competicao", "fase", "resultado", "oponente",
                                                      "pais_oponente")}
            meta.update(cor=cor, round=str(ri), anotador="automático (E5)", base_chave=(b or {}).get("chave", ""))
            docs.append({"meta": meta, "video": video,
                         "marcas": marcas_round(est[k], direcao[k], golpes[k], defesas[k], fps, ini, fim)})
    return docs



def main() -> None:
    import argparse
    import json
    import uuid
    from datetime import datetime
    from pathlib import Path

    import anotacao
    from base_mhds import carregar_base

    ap = argparse.ArgumentParser(description="E5: pré-anotação automática dos 4 estados (formato do modo juiz)")
    ap.add_argument("--resultado", default="outputs", help="pasta com eventos.json, serie.npz, deslocamento.csv")
    ap.add_argument("--rounds", required=True, type=float, nargs="+",
                    help="início de cada round no vídeo, em segundos (o round dura 180 s)")
    ap.add_argument("--video", default="", help="vídeo relativo a data/ (ex.: lutas/x.mp4), para abrir no modo juiz")
    ap.add_argument("--luta-id", default="", help="luta_id na base MHdS: preenche atletas e liga a comparação")
    ap.add_argument("--gravar", action="store_true", help="grava as pré-anotações em data/anotacoes/")
    args = ap.parse_args()

    base_luta = [r for r in carregar_base() if str(r["luta_id"]) == args.luta_id] if args.luta_id else None
    docs = anotar(args.resultado, args.rounds, args.video, base_luta)
    pasta = Path(__file__).resolve().parent.parent / "data" / "anotacoes"
    for doc in docs:
        doc = anotacao.validar(doc)
        r = anotacao.resumir(doc)
        m = doc["meta"]
        print(f"R{m['round']} {m['cor']:8s} {m['atleta'] or '-':14s} "
              + " · ".join(f"{e} {r['t_' + e]:.0f}s/{r['n_' + e]}" for e in anotacao.ESTADOS))
        if args.gravar:
            pasta.mkdir(parents=True, exist_ok=True)
            agora = datetime.now().isoformat(timespec="seconds")
            doc = {"id": uuid.uuid4().hex, "criado_em": agora, "atualizado_em": agora, **doc}
            (pasta / f"{doc['id']}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    if args.gravar:
        print(f"{len(docs)} pré-anotações em {pasta} — abra no modo juiz para revisar")


if __name__ == "__main__":
    main()
