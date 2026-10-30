"""E1 — modo juiz: anotação temporal de 1 atleta × 1 round (rotina da v1.0 com timestamps).

O anotador assiste ao vídeo devagar (padrão 0,125× = 8× mais lento, como na v1.0) e marca:
  - mudanças de ESTADO, mutuamente exclusivos: deslocamento (com direção opcional, no
    referencial do atleta), ataque, defesa, pausa (inclui clinch), fora (repetição da TV /
    corte — não conta no tempo do round) e fim do round;
  - AÇÕES pontuais: golpe e finta (ataque); bloqueio, esquiva e guarda (defesa). A
    pré-anotação automática (E5) usa "defesa" sem subtipo: ela não distingue os três.

resumir() transforma as marcas na linha da planilha v2.0 (mesmos campos da base MHdS, com o
clinch dentro da pausa) + o detalhamento novo (golpe × finta, bloqueio × esquiva × guarda,
direção do deslocamento). Contagens seguem as definições confirmadas da v1.0:
  n_deslocamento / n_pausa = nº de trechos contínuos do estado
  n_ataque = golpes + fintas;  n_defesa = bloqueios + esquivas + guarda
"""

from __future__ import annotations

import bisect
import csv
import io

ESTADOS = ("deslocamento", "ataque", "defesa", "pausa")
FORA, FIM = "fora", "fim"
DIRECOES = ("esq", "dir", "frente", "tras")
ACOES = {"golpe": "ataque", "finta": "ataque",
         "bloqueio": "defesa", "esquiva": "defesa", "guarda": "defesa", "defesa": "defesa"}
CAMPOS_META = ("atleta", "pais", "cor", "sexo", "categoria", "competicao", "fase",
               "resultado", "oponente", "pais_oponente", "round", "anotador", "base_chave")
MAX_MARCAS = 20_000
ROUND_MIN_S, ROUND_MAX_S = 175.0, 185.0

# linha da planilha v2.0 (as 4 primeiras de cada bloco batem com a base; o resto é novo)
COLUNAS_LINHA = [
    "round", "atleta", "pais", "cor", "sexo", "categoria", "competicao", "fase", "resultado",
    "oponente", "pais_oponente",
    "t_deslocamento", "t_ataque", "t_defesa", "t_pausa", "t_total",
    "n_deslocamento", "n_ataque", "n_defesa", "n_pausa",
    "n_golpes", "n_fintas", "n_bloqueios", "n_esquivas", "n_guarda", "n_defesa_sem_tipo",
    "n_sequencias_ataque",
    "t_desl_esq", "t_desl_dir", "t_desl_frente", "t_desl_tras", "t_desl_sem_dir",
    "n_desl_esq", "n_desl_dir", "n_desl_frente", "n_desl_tras",
    "t_fora", "inicio_round_s", "fim_round_s", "anotador", "video",
]

# anotação × base MHdS (base já convertida para v2.0: clinch somado à pausa)
COMPARAVEIS = [
    ("t_deslocamento", "t_deslocamento"), ("t_ataque", "t_ataque"), ("t_defesa", "t_defesa"),
    ("t_pausa", "t_pausa_v2"), ("t_total", "t_total"),
    ("n_deslocamento", "n_deslocamento"), ("n_ataque", "n_ataque"), ("n_defesa", "n_defesa"),
    ("n_pausa", "n_pausa_v2"),
]


def validar(doc: dict) -> dict:
    """Normaliza o JSON vindo da interface; levanta ValueError se estiver malformado."""
    if not isinstance(doc, dict):
        raise ValueError("anotação deve ser um objeto JSON")
    meta_in = doc.get("meta") or {}
    meta = {k: str(meta_in.get(k, "") or "").strip()[:200] for k in CAMPOS_META}
    marcas_in = doc.get("marcas") or []
    if not isinstance(marcas_in, list) or len(marcas_in) > MAX_MARCAS:
        raise ValueError("marcas inválidas")
    marcas = []
    for m in marcas_in:
        try:
            t = round(float(m["t"]), 3)
        except (KeyError, TypeError, ValueError):
            raise ValueError("marca sem tempo válido") from None
        if t < 0:
            raise ValueError("tempo negativo")
        if m.get("tipo") == "estado":
            estado = m.get("estado")
            if estado not in (*ESTADOS, FORA, FIM):
                raise ValueError(f"estado desconhecido: {estado}")
            d = m.get("dir") if estado == "deslocamento" else None
            if d not in (None, *DIRECOES):
                raise ValueError(f"direção desconhecida: {d}")
            marcas.append({"t": t, "tipo": "estado", "estado": estado, "dir": d})
        elif m.get("tipo") == "acao":
            if m.get("acao") not in ACOES:
                raise ValueError(f"ação desconhecida: {m.get('acao')}")
            marcas.append({"t": t, "tipo": "acao", "acao": m["acao"]})
        else:
            raise ValueError("tipo de marca deve ser 'estado' ou 'acao'")
    return {"meta": meta, "video": str(doc.get("video", "")), "marcas": marcas}


def segmentos(marcas: list[dict]) -> tuple[list[dict], bool]:
    """Intervalos [ini, fim) de estado a partir das marcas. Devolve (segmentos, aberto).

    Ordem estável: duas marcas no mesmo instante → vale a última inserida (a outra vira
    segmento de duração zero e é descartada). Sem marca de fim, o último segmento vai
    até a marca mais tardia (round em aberto).
    """
    est = sorted((m for m in marcas if m["tipo"] == "estado"), key=lambda m: m["t"])
    segs, aberto = [], True
    for i, m in enumerate(est):
        if m["estado"] == FIM:
            aberto = False
            break
        if i + 1 < len(est):
            fim = est[i + 1]["t"]
        else:
            fim = max(x["t"] for x in marcas)
        if fim > m["t"]:
            segs.append({"ini": m["t"], "fim": fim, "estado": m["estado"], "dir": m.get("dir")})
    return segs, aberto


def resumir(doc: dict) -> dict:
    """Marcas → campos da planilha v2.0 + avisos de consistência para o anotador."""
    marcas = doc.get("marcas", [])
    segs, aberto = segmentos(marcas)
    t = dict.fromkeys(ESTADOS, 0.0)
    trechos = dict.fromkeys(ESTADOS, 0)
    t_dir = dict.fromkeys((*DIRECOES, None), 0.0)
    n_dir = dict.fromkeys(DIRECOES, 0)
    t_fora = 0.0
    corridas: list[dict] = []  # trechos contínuos do mesmo estado (fora também quebra)
    ant_estado = ant_dir = None
    for s in segs:
        dur = s["fim"] - s["ini"]
        if s["estado"] != ant_estado:
            corridas.append({"ini": s["ini"], "fim": s["fim"], "estado": s["estado"], "acoes": 0})
        else:
            corridas[-1]["fim"] = s["fim"]
        if s["estado"] == FORA:
            t_fora += dur
        else:
            t[s["estado"]] += dur
            if s["estado"] != ant_estado:
                trechos[s["estado"]] += 1
            if s["estado"] == "deslocamento":
                t_dir[s["dir"]] += dur
                if s["dir"] and not (ant_estado == "deslocamento" and ant_dir == s["dir"]):
                    n_dir[s["dir"]] += 1
        ant_estado, ant_dir = s["estado"], s.get("dir")

    inicio = segs[0]["ini"] if segs else None
    fim = segs[-1]["fim"] if segs else None
    n_acao = dict.fromkeys(ACOES, 0)
    fora_do_round = fora_do_estado = 0
    inis = [c["ini"] for c in corridas]
    for m in marcas:
        if m["tipo"] != "acao":
            continue
        if inicio is None or not inicio <= m["t"] <= fim:
            fora_do_round += 1
            continue
        n_acao[m["acao"]] += 1
        c = corridas[max(bisect.bisect_right(inis, m["t"]) - 1, 0)]
        c["acoes"] += 1
        if c["estado"] != ACOES[m["acao"]]:
            fora_do_estado += 1

    t_total = sum(t.values())
    avisos = []
    if not segs:
        avisos.append("nenhum estado marcado — marque o início do round com 1–4 ou as setas")
    elif aberto:
        avisos.append("round em aberto — marque o fim com Enter")
    elif not ROUND_MIN_S <= t_total <= ROUND_MAX_S:
        avisos.append(f"tempo total {t_total:.1f} s (esperado ~180 s)")
    for estado, nome in (("ataque", "ataque"), ("defesa", "defesa")):
        vazios = sum(1 for c in corridas if c["estado"] == estado and c["acoes"] == 0)
        if vazios:
            avisos.append(f"{vazios} trecho(s) de {nome} sem nenhuma ação marcada")
    if fora_do_estado:
        avisos.append(f"{fora_do_estado} ação(ões) marcada(s) fora do estado correspondente")
    if fora_do_round:
        avisos.append(f"{fora_do_round} ação(ões) fora do round (antes do início/depois do fim)")

    r2 = lambda x: round(x, 2)  # noqa: E731
    return {
        "t_deslocamento": r2(t["deslocamento"]), "t_ataque": r2(t["ataque"]),
        "t_defesa": r2(t["defesa"]), "t_pausa": r2(t["pausa"]), "t_total": r2(t_total),
        "n_deslocamento": trechos["deslocamento"],
        "n_ataque": n_acao["golpe"] + n_acao["finta"],
        "n_defesa": n_acao["bloqueio"] + n_acao["esquiva"] + n_acao["guarda"] + n_acao["defesa"],
        "n_pausa": trechos["pausa"],
        "n_golpes": n_acao["golpe"], "n_fintas": n_acao["finta"],
        "n_bloqueios": n_acao["bloqueio"], "n_esquivas": n_acao["esquiva"],
        "n_guarda": n_acao["guarda"], "n_defesa_sem_tipo": n_acao["defesa"],
        "n_sequencias_ataque": trechos["ataque"],
        "t_desl_esq": r2(t_dir["esq"]), "t_desl_dir": r2(t_dir["dir"]),
        "t_desl_frente": r2(t_dir["frente"]), "t_desl_tras": r2(t_dir["tras"]),
        "t_desl_sem_dir": r2(t_dir[None]),
        "n_desl_esq": n_dir["esq"], "n_desl_dir": n_dir["dir"],
        "n_desl_frente": n_dir["frente"], "n_desl_tras": n_dir["tras"],
        "t_fora": r2(t_fora),
        "inicio_round_s": inicio, "fim_round_s": fim, "aberto": aberto,
        "avisos": avisos,
    }


def relogio_round(segs: list[dict], t: float) -> float:
    """Tempo de luta decorrido até o instante t do vídeo (exclui trechos 'fora')."""
    return sum((min(s["fim"], t) - s["ini"] for s in segs
               if s["estado"] != FORA and s["ini"] < t), 0.0)


def comparar(resumo: dict, base: dict | None) -> list[dict] | None:
    """Anotação × linha da base MHdS (v2.0): diferença absoluta por campo."""
    if not base:
        return None
    return [{"campo": a, "anotado": resumo[a], "base": base[b],
             "diferenca": round(resumo[a] - base[b], 2)} for a, b in COMPARAVEIS]


def linha(doc: dict, resumo: dict) -> dict:
    return {c: (resumo.get(c) if c in resumo else doc["meta"].get(c, doc.get(c, "")))
            for c in COLUNAS_LINHA}


def _csv(campos: list[str], linhas: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=campos, extrasaction="ignore")
    w.writeheader()
    w.writerows(linhas)
    return buf.getvalue()


def csv_linhas(docs: list[dict]) -> str:
    """Planilha v2.0: 1 linha por anotação (atleta × round)."""
    return _csv(COLUNAS_LINHA, [linha(d, resumir(d)) for d in docs])


def csv_intervalos(doc: dict) -> str:
    segs, _ = segmentos(doc["marcas"])
    return _csv(["inicio_s", "fim_s", "duracao_s", "relogio_round_s", "estado", "direcao"], [
        {"inicio_s": s["ini"], "fim_s": s["fim"], "duracao_s": round(s["fim"] - s["ini"], 3),
         "relogio_round_s": round(relogio_round(segs, s["ini"]), 3), "estado": s["estado"],
         "direcao": s["dir"] or ""} for s in segs])


def csv_acoes(doc: dict) -> str:
    segs, _ = segmentos(doc["marcas"])
    acoes = sorted((m for m in doc["marcas"] if m["tipo"] == "acao"), key=lambda m: m["t"])
    return _csv(["t_s", "relogio_round_s", "acao", "grupo"], [
        {"t_s": m["t"], "relogio_round_s": round(relogio_round(segs, m["t"]), 3), "acao": m["acao"],
         "grupo": ACOES[m["acao"]]} for m in acoes])
