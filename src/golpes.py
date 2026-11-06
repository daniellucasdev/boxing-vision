"""Tipo de golpe por regras sobre a pose: jab, direto, cruzado (hook) e gancho (uppercut).

Entra a saída do pipeline (eventos.json com os golpes detectados + serie.npz com os 17
keypoints de cada canto por quadro) e sai, para cada golpe, o tipo e a mão (da frente / de
trás), ou "sem tipo" quando a pose não permite decidir. Grava golpes.json na mesma pasta; a E5
(estados.anotar) usa esse arquivo para a pré-anotação do modo juiz já chegar com o tipo.

Regras (vídeo 2D, câmera de transmissão, quase sempre de lado para o confronto):
  - MÃO: guarda do atleta = lado do corpo mais próximo do oponente ao longo do eixo entre os
    dois (tornozelos; sem eles, quadris; sem eles, ombros), em mediana numa janela de
    GUARDA_JANELA_S. Mão do golpe = frente se o braço do golpe é desse lado. Se o YOLO trocar
    esquerda e direita (atleta de costas), troca guarda e braço juntos e a mão continua certa.
  - TRAJETÓRIA, na janela de ±JANELA_S em volta do golpe, medida em troncos (ombros → quadris,
    que não encolhe quando o atleta gira como a largura dos ombros):
      o punho é medido RELATIVO ao ombro (desconta o corpo que avança junto); "alcance" é a
      projeção punho − ombro no eixo até o oponente (o braço caído longe do ombro não alcança);
      gancho  = punho sobe 2× mais do que avança, de abaixo do ombro até a altura do queixo,
                com o cotovelo dobrado e perto do corpo no topo;
      reto    = cotovelo estendido no alcance máximo (≥ COTOVELO_RETO), punho avançando e
                ≥ ALCANCE_RETO à frente do ombro;
      cruzado = cotovelo dobrado (≤ COTOVELO_DOBRADO) e alto, punho na altura do ombro.
    O arco horizontal do cruzado acontece em profundidade e não aparece de lado; o que aparece
    é o cotovelo dobrado e alto. Entre COTOVELO_DOBRADO e COTOVELO_RETO fica sem tipo.
  - Keypoints de braço com confiança baixa, braço muito encurtado na tela (golpe na direção
    da câmera), corte de câmera na janela (lista de cortes do pipeline ou ombro que "teleporta")
    ou guarda indefinida → sem tipo.

Limiares: valores de partida, a calibrar com golpes revisados (P13). Não há gabarito na base
MHdS, que não registra o tipo de golpe.

CLI:
  python src/golpes.py --resultado outputs/lutas/pan2023_final_92kg_lacruz_x_keno
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np

# COCO-17
L_SHOULDER, R_SHOULDER, L_ELBOW, R_ELBOW, L_WRIST, R_WRIST = 5, 6, 7, 8, 9, 10
L_HIP, R_HIP, L_ANKLE, R_ANKLE = 11, 12, 15, 16
BRACO = {"L": (L_SHOULDER, L_ELBOW, L_WRIST), "R": (R_SHOULDER, R_ELBOW, R_WRIST)}
CORES = ("Vermelho", "Azul")

MIN_CONF = 0.3
JANELA_S = 0.25          # ± em volta do pico de velocidade (ação dura ~0,45 s na base)
GUARDA_JANELA_S = 2.0    # ± para a mediana da guarda (há troca de guarda no round)
GUARDA_MIN = 0.08        # |frente(esq) − frente(dir)| mínimo, em troncos, para o quadro votar
GUARDA_MIN_VOTOS = 5     # quadros com voto na janela para decidir a guarda
COTOVELO_RETO = 145.0    # graus no alcance máximo
COTOVELO_DOBRADO = 130.0
AVANCO_RETO = 0.25       # troncos que o punho avança (relativo ao ombro) no reto
ALCANCE_RETO = 0.60      # punho ≥ 0,6 tronco à frente do ombro, na direção do oponente
SUBIDA_MIN = 0.35        # troncos que o punho sobe no gancho
GANCHO_DOMINANCIA = 2.0  # no gancho o punho sobe 2× mais do que avança (jab de mão baixa também sobe)
GANCHO_COTOVELO = 120.0  # cotovelo dobrado no ponto mais alto
GANCHO_ALCANCE = 0.55    # e o punho perto do corpo (não esticado na direção do oponente)
GANCHO_PARTIDA = 0.30    # parte ≥ 0,3 tronco abaixo do ombro
GANCHO_TOPO = 0.15       # e termina na altura do queixo (≤ 0,15 tronco abaixo do ombro)
AVANCO_CRUZADO = 0.15
COTOVELO_ALTO = -0.35    # cotovelo no máx. 0,35 tronco abaixo do ombro no cruzado
PUNHO_ALTURA_CRUZADO = 0.35  # punho na altura do ombro (±0,35 tronco) no alcance máximo
SALTO_MAX = 1.0          # troncos que o ombro anda por quadro; acima = corte ou troca de pessoa (mediana 0,17)
BRACO_MIN = 0.45         # ombro→punho no alcance máx. (troncos); menos que isso = escorço forte


def _ok(k: np.ndarray, *idx: int) -> bool:
    return bool(np.all(np.isfinite(k[list(idx), :2])) and np.all(k[list(idx), 2] >= MIN_CONF))


def _meio(k: np.ndarray, a: int, b: int) -> np.ndarray:
    return (k[a, :2] + k[b, :2]) / 2


def _tronco(k: np.ndarray) -> float | None:
    if not _ok(k, L_SHOULDER, R_SHOULDER, L_HIP, R_HIP):
        return None
    t = float(np.linalg.norm(_meio(k, L_SHOULDER, R_SHOULDER) - _meio(k, L_HIP, R_HIP)))
    return t if t > 4 else None


def _eixo(k: np.ndarray, opp: np.ndarray) -> np.ndarray | None:
    """Direção (unitária, na tela) do atleta até o oponente, pelo meio dos ombros."""
    if not (_ok(k, L_SHOULDER, R_SHOULDER) and _ok(opp, L_SHOULDER, R_SHOULDER)):
        return None
    v = _meio(opp, L_SHOULDER, R_SHOULDER) - _meio(k, L_SHOULDER, R_SHOULDER)
    n = float(np.linalg.norm(v))
    return v / n if n > 1 else None


def voto_guarda(k: np.ndarray, opp: np.ndarray) -> str | None:
    """'L' se o lado esquerdo do atleta está à frente (ortodoxo), 'R' se o direito; None = não dá."""
    u, t = _eixo(k, opp), _tronco(k)
    if u is None or t is None:
        return None
    for a, b in ((L_ANKLE, R_ANKLE), (L_HIP, R_HIP), (L_SHOULDER, R_SHOULDER)):
        if _ok(k, a, b):
            d = float((k[a, :2] - k[b, :2]) @ u) / t
            if abs(d) >= GUARDA_MIN:
                return "L" if d > 0 else "R"
            return None  # o par mais confiável existe e está ambíguo: não cair para o próximo
    return None


def guardas(kps: np.ndarray, fps: float) -> list[list[str | None]]:
    """Guarda de cada canto por quadro (mediana dos votos em ±GUARDA_JANELA_S)."""
    n = len(kps)
    out: list[list[str | None]] = []
    w = max(1, round(GUARDA_JANELA_S * fps))
    for k in range(2):
        votos = np.array([{"L": 1, "R": -1}.get(voto_guarda(kps[f, k], kps[f, 1 - k]), 0) for f in range(n)])
        soma, cont = np.cumsum(np.r_[0, votos]), np.cumsum(np.r_[0, votos != 0])
        g = []
        for f in range(n):
            a, b = max(0, f - w), min(n, f + w + 1)
            s, c = soma[b] - soma[a], cont[b] - cont[a]
            g.append(None if c < GUARDA_MIN_VOTOS or s == 0 else ("L" if s > 0 else "R"))
        out.append(g)
    return out


def _angulo(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    v1, v2 = a - b, c - b
    cos = float(v1 @ v2 / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-9))
    return float(np.degrees(np.arccos(np.clip(cos, -1.0, 1.0))))


def medidas(kps: np.ndarray, k: int, f: int, braco: str, fps: float) -> dict | None:
    """Medidas da trajetória do braço em volta do quadro f (0-based). None = pose insuficiente.

    Tudo é medido no punho RELATIVO ao ombro do mesmo lado (desconta o corpo que avança junto) e
    em troncos. "Alcance" = projeção punho − ombro no eixo até o oponente: o braço caído ao lado
    do corpo fica longe do ombro, mas não alcança nada (a distância pura confundia os dois).
    """
    s_i, e_i, w_i = BRACO[braco]
    w = max(2, round(JANELA_S * fps))
    ini, fim = max(0, f - w), min(len(kps), f + w + 1)
    jan, opp = kps[ini:fim, k], kps[ini:fim, 1 - k]
    ok = [i for i in range(len(jan)) if _ok(jan[i], s_i, e_i, w_i)]
    troncos = [t for t in (_tronco(x) for x in jan) if t is not None]
    eixos = [u for u in (_eixo(jan[i], opp[i]) for i in range(len(jan))) if u is not None]
    if len(ok) < max(3, len(jan) // 2) or not troncos or not eixos:
        return None
    t = float(np.median(troncos))
    # corte de câmera que o detector de cortes não pegou (replay, fusão): o ombro "teleporta"
    # (por quadro: lacunas sem pose entre dois quadros válidos não contam como salto)
    ombros = np.array([_meio(jan[i], L_SHOULDER, R_SHOULDER) for i in ok])
    if len(ok) > 1:
        passo = np.linalg.norm(np.diff(ombros, axis=0), axis=1) / np.diff(ok)
        if float(passo.max()) / t > SALTO_MAX:
            return None
    u = np.mean(eixos, axis=0)
    u = u / (np.linalg.norm(u) + 1e-9)
    rel = {i: (jan[i, w_i, :2] - jan[i, s_i, :2]) / t for i in ok}
    alc = {i: float(rel[i] @ u) for i in ok}
    pico = f - ini
    depois = [i for i in ok if i >= pico - w // 2]
    if not depois:
        return None
    # reto/cruzado: máximo alcance depois do início do golpe; o mínimo antes dele é a partida
    i_max = max(depois, key=alc.get)
    antes = [i for i in ok if i <= i_max]
    i_min = min(antes, key=alc.get)
    # gancho: ponto mais alto do punho (relativo ao ombro) e o mais baixo antes dele
    i_alto = min(depois, key=lambda i: rel[i][1])     # y da tela cresce para baixo
    i_baixo = max((i for i in ok if i <= i_alto), key=lambda i: rel[i][1])
    a, topo = jan[i_max], jan[i_alto]
    return {
        "extensao": round(float(np.linalg.norm(rel[i_max])), 3),
        "alcance": round(alc[i_max], 3),
        "cotovelo": round(_angulo(a[s_i, :2], a[e_i, :2], a[w_i, :2]), 1),
        "avanco": round(alc[i_max] - alc[i_min], 3),
        "subida": round(float(rel[i_baixo][1] - rel[i_alto][1]), 3),
        "punho_ini_abaixo_ombro": round(float(rel[i_baixo][1]), 3),
        "punho_topo": round(float(rel[i_alto][1]), 3),          # + = abaixo do ombro
        "alcance_topo": round(alc[i_alto], 3),
        "cotovelo_topo": round(_angulo(topo[s_i, :2], topo[e_i, :2], topo[w_i, :2]), 1),
        "punho_pico_altura": round(float(rel[i_max][1]), 3),
        "cotovelo_altura": round(float(a[s_i, 1] - a[e_i, 1]) / t, 3),
    }


def trajetoria(m: dict | None) -> str | None:
    """'reto' | 'cruzado' | 'gancho' | None a partir das medidas."""
    if m is None or m["extensao"] < BRACO_MIN:
        return None
    if (m["subida"] >= SUBIDA_MIN and m["subida"] >= GANCHO_DOMINANCIA * max(m["avanco"], 0.0)
            and m["punho_ini_abaixo_ombro"] >= GANCHO_PARTIDA and m["punho_topo"] <= GANCHO_TOPO
            and m["cotovelo_topo"] <= GANCHO_COTOVELO and m["alcance_topo"] <= GANCHO_ALCANCE):
        return "gancho"
    if m["cotovelo"] >= COTOVELO_RETO and m["avanco"] >= AVANCO_RETO and m["alcance"] >= ALCANCE_RETO:
        return "reto"
    if (m["cotovelo"] <= COTOVELO_DOBRADO and m["cotovelo_altura"] >= COTOVELO_ALTO
            and m["avanco"] >= AVANCO_CRUZADO and abs(m["punho_pico_altura"]) <= PUNHO_ALTURA_CRUZADO):
        return "cruzado"
    return None


def tipo_golpe(traj: str | None, braco: str, guarda: str | None) -> dict:
    """{'golpe', 'mao'} no formato do modo juiz, ou {} (golpe sem tipo)."""
    if traj is None or guarda is None:
        return {}
    mao = "frente" if braco == guarda else "tras"
    if traj == "reto":
        return {"golpe": "jab" if mao == "frente" else "direto", "mao": mao}
    return {"golpe": traj, "mao": mao}


def classificar(out_dir) -> list[dict]:
    """Golpes do eventos.json com tipo, mão e as medidas usadas."""
    out_dir = Path(out_dir)
    z = np.load(out_dir / "serie.npz")
    if "kps" not in z:
        raise SystemExit(f"{out_dir}/serie.npz não tem keypoints: rode o pipeline de novo (features.py --save)")
    kps, fps = z["kps"], float(z["fps"])
    ev = json.loads((out_dir / "eventos.json").read_text())
    eventos, cortes = ev["eventos"], np.array(ev.get("cortes", []), dtype=int)
    janela = max(2, round(JANELA_S * fps))
    g = guardas(kps, fps)
    out = []
    for e in eventos:
        k, f = CORES.index(e["boxer"]), int(e["frame"]) - 1
        if not 0 <= f < len(kps):
            continue
        perto_de_corte = bool(len(cortes)) and bool(np.any(np.abs(cortes - int(e["frame"])) <= janela))
        m = None if perto_de_corte else medidas(kps, k, f, e["braco"], fps)
        traj = trajetoria(m)
        out.append({"frame": int(e["frame"]), "boxer": e["boxer"], "braco": e["braco"],
                    "guarda": g[k][f], "trajetoria": traj, **tipo_golpe(traj, e["braco"], g[k][f]),
                    "corte": perto_de_corte, "medidas": m})
    return out


# ---------------------------------------------------------------------------------------------
# revisão humana (página /golpes): gabarito por golpe detectado
# ---------------------------------------------------------------------------------------------

REVISADOS = Path(__file__).resolve().parent.parent / "data" / "golpes_revisados"
# rótulo da revisão → (golpe, mão) no formato do modo juiz; os 3 últimos não são golpe tipado
ROTULOS = {"jab": ("jab", "frente"), "direto": ("direto", "tras"),
           "cruzado_frente": ("cruzado", "frente"), "cruzado_tras": ("cruzado", "tras"),
           "gancho_frente": ("gancho", "frente"), "gancho_tras": ("gancho", "tras"),
           "finta": None, "nao_golpe": None, "incerto": None}


def golpe_id(g: dict) -> str:
    """Identificador estável de um golpe detectado: V1102L = Vermelho, quadro 1102, braço L."""
    return f"{g['boxer'][0]}{int(g['frame'])}{g['braco']}"


def rotulo_auto(g: dict) -> str | None:
    """Rótulo da revisão equivalente à saída automática (None = sem tipo)."""
    if not g.get("golpe"):
        return None
    return g["golpe"] if g["golpe"] in ("jab", "direto") else f"{g['golpe']}_{g['mao']}"


def ler_revisao(nome: str) -> dict:
    p = REVISADOS / f"{nome}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"luta": nome, "rotulos": {}}


def gravar_rotulo(nome: str, gid: str, rotulo: str | None, quando: str) -> dict:
    """Grava (ou apaga, com rotulo=None) o rótulo de um golpe. Escrita atômica."""
    import os
    if rotulo is not None and rotulo not in ROTULOS:
        raise ValueError(f"rótulo desconhecido: {rotulo}")
    rev = ler_revisao(nome)
    if rotulo is None:
        rev["rotulos"].pop(gid, None)
    else:
        rev["rotulos"][gid] = {"rotulo": rotulo, "em": quando}
    REVISADOS.mkdir(parents=True, exist_ok=True)
    p = REVISADOS / f"{nome}.json"
    tmp = p.with_suffix(".partial")
    tmp.write_text(json.dumps(rev, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)
    return rev


def resumo(golpes: list[dict]) -> dict:
    por = {}
    for c in CORES:
        gs = [x for x in golpes if x["boxer"] == c]
        cont = Counter((x.get("golpe"), x.get("mao")) for x in gs)
        guarda = Counter(x["guarda"] for x in gs)
        por[c] = {"golpes": len(gs),
                  "tipos": {f"{g}_{m}" if g else "sem_tipo": n for (g, m), n in cont.most_common()},
                  "guarda": {str(k): n for k, n in guarda.most_common()},
                  "sem_medida": sum(x["medidas"] is None for x in gs)}
    return por


def main() -> None:
    ap = argparse.ArgumentParser(description="tipo de golpe por regras → golpes.json")
    ap.add_argument("--resultado", default="outputs", help="pasta com eventos.json e serie.npz")
    args = ap.parse_args()
    golpes = classificar(args.resultado)
    destino = Path(args.resultado) / "golpes.json"
    params = {k: v for k, v in globals().items() if k.isupper() and isinstance(v, (int, float))}
    destino.write_text(json.dumps({"params": params, "golpes": golpes}, ensure_ascii=False, indent=1))
    for c, r in resumo(golpes).items():
        sem = r["tipos"].get("sem_tipo", 0)
        print(f"{c:8s} {r['golpes']} golpes · sem tipo {sem} ({100 * sem / max(r['golpes'], 1):.0f}%) · "
              f"guarda {r['guarda']}")
        print("         " + " · ".join(f"{k} {n}" for k, n in r["tipos"].items() if k != "sem_tipo"))
    print(f"→ {destino}")


if __name__ == "__main__":
    main()
