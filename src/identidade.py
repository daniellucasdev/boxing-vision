"""E3 — identidade dos atletas pela cor do uniforme (Azul × Vermelho) e cortes de câmera.

No boxe olímpico cada atleta veste colete, calção e luvas da cor do canto (azul ou
vermelho). Em vez de seguir "o slot mais próximo" (v3), cada detecção de pose recebe
uma cor medida SÓ nas regiões do corpo que o esqueleto aponta:

  - tronco: quadrilátero ombros→quadris, encolhido para o centro (fora a pele dos
    braços e o fundo);
  - calção: faixa dos quadris até ~40% da coxa;
  - luvas: círculos em volta dos punhos.

Medir na caixa inteira falharia: o ringue do Pan 2023 é azul, a arquibancada de
Tóquio é vermelha. Juiz (camisa branca) e plateia ficam sem cor. A comissão técnica
de vermelho é barrada pelo gate de escala/posição em features.py.

Cortes de câmera: diferença média de pixels (cinza 64×36) entre quadros consecutivos,
ou queda brusca na correlação do histograma HSV. Trocas entre câmeras do mesmo ringue
mantêm o histograma (correlação 0,74–0,99) — só a diferença de pixels as pega.
"""

from __future__ import annotations

import cv2
import numpy as np

# COCO-17
L_SHOULDER, R_SHOULDER = 5, 6
L_WRIST, R_WRIST = 9, 10
L_HIP, R_HIP = 11, 12
L_KNEE, R_KNEE = 13, 14

MIN_CONF = 0.3
ENCOLHE_TRONCO = 0.30   # fração da distância ao centro removida das bordas do tronco
RAIO_LUVA = 0.40        # × largura dos ombros
ALTURA_TRONCO = 0.55    # fração ombro→quadril usada como tronco
PESOS = {"tronco": 1.0, "calcao": 0.6, "luvas": 0.5}

# HSV do OpenCV (H 0–179). Calibrado em data/lutas (Pan 2023, Tóquio 2020) e olympic.mp4.
S_MIN, V_MIN = 110, 50
H_VERMELHO = ((0, 7), (168, 179))
H_AZUL = ((100, 128),)
FRACAO_MIN = 0.22       # fração mínima de pixels da cor para decidir
DOMINANCIA = 2.0        # a cor vencedora precisa ter ≥ 2× a outra
TRONCO_MIN = 0.12       # o tronco sozinho precisa confirmar a cor (luva de látex azul do juiz)

CORTE_CORRELACAO = 0.55
CORTE_DIFERENCA = 0.12  # MAD/255; calibrado na final do Pan 2023 (p99 do movimento = 0,07)


def _mascara_hue(hsv: np.ndarray, faixas) -> np.ndarray:
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    m = np.zeros(h.shape, bool)
    for lo, hi in faixas:
        m |= (h >= lo) & (h <= hi)
    return m & (s >= S_MIN) & (v >= V_MIN)


def _ok(kps: np.ndarray, *idx: int) -> bool:
    return all(kps[i][2] >= MIN_CONF for i in idx)


def regioes(kps: np.ndarray, shape: tuple[int, int]) -> dict[str, np.ndarray]:
    """Máscaras booleanas (H×W) de tronco, calção e luvas para uma detecção."""
    h, w = shape
    out: dict[str, np.ndarray] = {}
    if not _ok(kps, L_SHOULDER, R_SHOULDER):
        return out
    ls, rs = kps[L_SHOULDER][:2], kps[R_SHOULDER][:2]
    sw = float(np.linalg.norm(ls - rs))
    if sw < 4:
        return out
    if _ok(kps, L_HIP, R_HIP):
        lh, rh = kps[L_HIP][:2], kps[R_HIP][:2]
    else:
        # quadris ocultos (close, juiz sentado atrás do avental do ringue): só a parte de
        # cima do peito — estender até a cintura estimada pegava o avental azul
        baixo = np.array([0, 0.7 * sw])
        lh, rh = ls + baixo, rs + baixo
    # só a metade de cima do tronco: com o quadril oculto o modelo "chuta" o quadril
    # dentro do avental azul do ringue (juízes sentados) — o calção cobre a parte de baixo
    lh, rh = ls + ALTURA_TRONCO * (lh - ls), rs + ALTURA_TRONCO * (rh - rs)
    quad = np.array([ls, rs, rh, lh], np.float32)
    centro = quad.mean(axis=0)
    quad = centro + (quad - centro) * (1 - ENCOLHE_TRONCO)
    m = np.zeros((h, w), np.uint8)
    cv2.fillPoly(m, [quad.astype(np.int32)], 1)
    out["tronco"] = m.astype(bool)

    if _ok(kps, L_HIP, R_HIP) and _ok(kps, L_KNEE, R_KNEE):
        lh, rh = kps[L_HIP][:2], kps[R_HIP][:2]
        lk, rk = kps[L_KNEE][:2], kps[R_KNEE][:2]
        faixa = np.array([lh, rh, rh + 0.4 * (rk - rh), lh + 0.4 * (lk - lh)], np.float32)
        c = faixa.mean(axis=0)
        faixa = c + (faixa - c) * 0.8
        m = np.zeros((h, w), np.uint8)
        cv2.fillPoly(m, [faixa.astype(np.int32)], 1)
        out["calcao"] = m.astype(bool)

    m = np.zeros((h, w), np.uint8)
    for i in (L_WRIST, R_WRIST):
        if kps[i][2] >= MIN_CONF:
            cv2.circle(m, tuple(int(v) for v in kps[i][:2]), max(2, int(RAIO_LUVA * sw)), 1, -1)
    if m.any():
        out["luvas"] = m.astype(bool)
    return out


def mascaras_cor(hsv: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Pixels vermelhos e azuis saturados do quadro (calcular 1× por quadro)."""
    return _mascara_hue(hsv, H_VERMELHO), _mascara_hue(hsv, H_AZUL)


def medir_cor(hsv: np.ndarray, kps: np.ndarray, mascaras=None) -> dict:
    """Frações ponderadas de vermelho/azul nas regiões do corpo + decisão.

    Devolve {"vermelho": f, "azul": f, "cor": "Vermelho"|"Azul"|None, "confianca": 0–1}.
    """
    reg = regioes(kps, hsv.shape[:2])
    if "tronco" not in reg:
        return {"vermelho": 0.0, "azul": 0.0, "cor": None, "confianca": 0.0}
    mv, ma = mascaras if mascaras is not None else mascaras_cor(hsv)
    fv = fa = peso = 0.0
    tronco = {"Vermelho": 0.0, "Azul": 0.0}
    for nome, m in reg.items():
        n = int(m.sum())
        if n < 12:
            continue
        p = PESOS[nome]
        rv, ra = float((mv & m).sum()) / n, float((ma & m).sum()) / n
        if nome == "tronco":
            tronco = {"Vermelho": rv, "Azul": ra}
        fv += p * rv
        fa += p * ra
        peso += p
    if peso == 0:
        return {"vermelho": 0.0, "azul": 0.0, "cor": None, "confianca": 0.0}
    fv, fa = fv / peso, fa / peso
    cor = None
    if fv >= FRACAO_MIN and fv >= DOMINANCIA * fa:
        cor = "Vermelho"
    elif fa >= FRACAO_MIN and fa >= DOMINANCIA * fv:
        cor = "Azul"
    if cor and tronco[cor] < TRONCO_MIN:
        cor = None
    conf = abs(fv - fa) / max(fv + fa, 1e-6) * min(1.0, max(fv, fa) / 0.5)
    return {"vermelho": round(fv, 3), "azul": round(fa, 3), "cor": cor, "confianca": round(conf, 3)}


class DetectorCortes:
    """Corte de câmera = salto na diferença de pixels ou queda na correlação do histograma."""

    def __init__(self, limiar_corr: float = CORTE_CORRELACAO, limiar_dif: float = CORTE_DIFERENCA) -> None:
        self.limiar_corr, self.limiar_dif = limiar_corr, limiar_dif
        self.hist: np.ndarray | None = None
        self.cinza: np.ndarray | None = None

    def atualizar(self, hsv: np.ndarray) -> tuple[bool, float]:
        """Devolve (é corte?, diferença média de pixels 0–1)."""
        pequeno = cv2.resize(hsv, (160, 90), interpolation=cv2.INTER_AREA)
        hist = cv2.calcHist([pequeno], [0, 1], None, [30, 16], [0, 180, 0, 256])
        cv2.normalize(hist, hist)
        cinza = cv2.resize(hsv[..., 2], (64, 36), interpolation=cv2.INTER_AREA).astype(np.float32)
        if self.hist is None:
            self.hist, self.cinza = hist, cinza
            return False, 0.0
        corr = float(cv2.compareHist(self.hist, hist, cv2.HISTCMP_CORREL))
        dif = float(np.abs(cinza - self.cinza).mean()) / 255
        self.hist, self.cinza = hist, cinza
        return dif >= self.limiar_dif or corr < self.limiar_corr, dif
