"""E4 — deslocamento: compensação do movimento da câmera + direção em relação ao oponente.

A câmera da transmissão segue a luta (pan, tilt, zoom), então o movimento do atleta na
tela mistura o dele com o da câmera. Três passos:

1. Câmera: pontos de textura do FUNDO (pessoas mascaradas) seguidos por fluxo óptico entre
   quadros consecutivos → similaridade (translação + escala + rotação) por RANSAC. Os
   gráficos da TV (placar, logos) ficam parados na tela mesmo com a câmera andando; quando
   um grupo de pontos se move de forma coerente, ele vence os pontos "colados" na tela.
2. Atleta: ponto no chão = meio dos tornozelos (sem os pés no quadro, não mede). O
   histórico desse ponto é transportado pelo movimento da câmera a cada quadro, então a reta ajustada aos últimos 0,5 s já vem descontada da câmera. A unidade é a
   altura do próprio atleta na tela, estimada pelo tronco (corpos/s): invariante ao zoom
   e à profundidade.
3. Direção: eixo = do atleta até o oponente. Frente/trás = componente ao longo do eixo;
   esquerda/direita = componente perpendicular, do ponto de vista do atleta (ele encara o
   oponente). A câmera fica acima do ringue, então a tela é uma vista de cima sem espelho,
   só achatada na profundidade (escorço): o vertical da tela é dividido por ESCORCO.

ESCORCO veio da geometria do ringue (quadrado de 6,1 m): os 4 cantos num plano aberto da
câmera principal do Pan 2023 dão uma homografia, e no centro do ringue 1 m em profundidade
aparece com 0,33 do tamanho de 1 m na horizontal (0,30–0,38 do fundo para a frente; igual
nas duas lutas medidas). Estimar por vídeo pela distância entre os atletas não funcionou:
essa distância varia demais por si só (de 0,22 a 1,0 conforme o trecho).
"""

from __future__ import annotations

from collections import deque

import cv2
import numpy as np

# COCO-17
L_SHOULDER, R_SHOULDER = 5, 6
L_HIP, R_HIP = 11, 12
L_ANKLE, R_ANKLE = 15, 16
MIN_CONF = 0.3

# --- câmera ---
LARGURA_FLUXO = 320     # o fluxo é calculado numa cópia reduzida do quadro
MAX_PONTOS = 300
MIN_PONTOS = 15
COLADO_PX = 0.15        # fluxo menor que isso (na escala reduzida) = parado na tela
MIN_SUPORTE = 0.25      # fração dos pontos que precisa concordar com o movimento da câmera
MARGEM_CAIXA = 0.10     # máscara das pessoas: caixa aumentada em 10%

# --- atleta ---
JANELA_S = 0.5          # velocidade = inclinação da reta ajustada aos pontos dessa janela
MIN_JANELA = 0.6        # fração mínima da janela com pontos para medir
RAZAO_TRONCO = 0.285    # tronco (meio dos ombros → meio dos quadris) ÷ altura; mediana medida no Pan 2023
VEL_MAX = 2.5           # corpos/s (~4,5 m/s): acima disso é salto de keypoint, não passo
PERNA_TRONCOS = 1.47    # pés ficam 1,47 tronco abaixo do quadril na tela (mediana, Pan 2023)
MARGEM_BORDA = 0.03     # pé a menos de 3% da borda de baixo = cortado; o YOLO "inventa" o tornozelo

# --- direção ---
ESCORCO = 0.33          # profundidade ÷ horizontal no chão, câmera principal (ver docstring)
MIN_VEL = 0.25          # corpos/s (~0,45 m/s): abaixo disso, parado
SUAVIZA = 7             # quadros do filtro de moda dos rótulos
MIN_DURACAO_S = 0.2     # trecho de direção mais curto que conta em n_
DIRECOES = ("frente", "tras", "esq", "dir")


class CompensadorCamera:
    """Movimento da câmera entre quadros consecutivos (pan, tilt, zoom)."""

    def __init__(self) -> None:
        self.cinza: np.ndarray | None = None
        self.mascara: np.ndarray | None = None

    def reset(self) -> None:
        self.cinza = None

    def atualizar(self, quadro_bgr: np.ndarray, caixas) -> np.ndarray | None:
        """Matriz 2×3 que leva pontos do quadro anterior para o atual (pixels do quadro
        original), ou None sem quadro anterior / sem fundo suficiente."""
        h, w = quadro_bgr.shape[:2]
        esc = LARGURA_FLUXO / w
        pequeno = cv2.resize(quadro_bgr, (LARGURA_FLUXO, round(h * esc)), interpolation=cv2.INTER_AREA)
        cinza = cv2.cvtColor(pequeno, cv2.COLOR_BGR2GRAY)
        mascara = np.full(cinza.shape, 255, np.uint8)
        for x1, y1, x2, y2 in caixas:
            mx, my = MARGEM_CAIXA * (x2 - x1), MARGEM_CAIXA * (y2 - y1)
            mascara[max(0, int((y1 - my) * esc)):int((y2 + my) * esc) + 1,
                    max(0, int((x1 - mx) * esc)):int((x2 + mx) * esc) + 1] = 0
        M = None
        if self.cinza is not None:
            M = self._estimar(self.cinza, cinza, self.mascara)
        self.cinza, self.mascara = cinza, mascara
        if M is None:
            return None
        M = M.copy()
        M[:, 2] /= esc
        return M

    @staticmethod
    def _estimar(antes: np.ndarray, agora: np.ndarray, mascara: np.ndarray) -> np.ndarray | None:
        pts = cv2.goodFeaturesToTrack(antes, MAX_PONTOS, 0.01, 6, mask=mascara)
        if pts is None or len(pts) < MIN_PONTOS:
            return None
        lk = {"winSize": (21, 21), "maxLevel": 3}
        nxt, st, _ = cv2.calcOpticalFlowPyrLK(antes, agora, pts, None, **lk)
        volta, st2, _ = cv2.calcOpticalFlowPyrLK(agora, antes, nxt, None, **lk)
        ok = (st.ravel() == 1) & (st2.ravel() == 1) & (np.linalg.norm(volta - pts, axis=2).ravel() < 0.5)
        a, b = pts[ok].reshape(-1, 2), nxt[ok].reshape(-1, 2)
        if len(a) < MIN_PONTOS:
            return None
        colados = np.linalg.norm(b - a, axis=1) < COLADO_PX
        minimo = max(MIN_PONTOS, MIN_SUPORTE * len(a))
        moveis = ~colados
        if moveis.sum() >= minimo:
            M, inl = cv2.estimateAffinePartial2D(a[moveis], b[moveis], method=cv2.RANSAC,
                                                 ransacReprojThreshold=1.0)
            if M is not None and inl is not None and inl.sum() >= minimo:
                return M
        # câmera parada só com maioria parada: placar e logos sozinhos não bastam
        if colados.sum() >= max(MIN_PONTOS, 0.5 * len(a)):
            return np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
        return None


def ponto_chao(kps: np.ndarray, altura_quadro: int | None = None) -> tuple[np.ndarray, str] | None:
    """Ponto do atleta no chão: meio dos tornozelos. Sem os pés no quadro, não mede.

    O quadril NÃO serve de reserva: ao esquivar ou se levantar, ele sobe e desce na tela,
    e o vertical da tela é profundidade ampliada por 1/ESCORCO (~3×) — uma esquiva virava
    "recuou meio corpo".
    """
    if kps[L_ANKLE][2] < MIN_CONF or kps[R_ANKLE][2] < MIN_CONF:
        return None
    if altura_quadro and max(kps[L_ANKLE][1], kps[R_ANKLE][1]) > (1 - MARGEM_BORDA) * altura_quadro:
        return None
    return (kps[L_ANKLE][:2] + kps[R_ANKLE][:2]) / 2, "tornozelos"


def escala_corpo(kps: np.ndarray, caixa) -> float | None:
    """Altura do corpo na tela (px), estimada pelo tronco.

    A caixa da pessoa não serve sozinha: em plano fechado ela é cortada pela borda da
    tela e o atleta "encolhe", inflando a velocidade. Sem tronco visível, usa a caixa só
    se os pés estão no quadro.
    """
    if all(kps[i][2] >= MIN_CONF for i in (L_SHOULDER, R_SHOULDER, L_HIP, R_HIP)):
        ombros = (kps[L_SHOULDER][:2] + kps[R_SHOULDER][:2]) / 2
        quadris = (kps[L_HIP][:2] + kps[R_HIP][:2]) / 2
        tronco = float(np.linalg.norm(ombros - quadris))
        if tronco > 4:
            return tronco / RAZAO_TRONCO
    if kps[L_ANKLE][2] >= MIN_CONF and kps[R_ANKLE][2] >= MIN_CONF:
        return float(caixa[3] - caixa[1])
    return None


def pes_estimados(kps: np.ndarray, altura_quadro: int | None = None) -> tuple[np.ndarray, str] | None:
    """Onde estão os pés, para o EIXO até o oponente (só a direção importa).

    Pés fora do quadro → quadril + PERNA_TRONCOS troncos para baixo. Bom para direção
    (erro ~±0,05 corpo na vertical), não para velocidade: por isso ponto_chao não usa.
    """
    pe = ponto_chao(kps, altura_quadro)
    if pe is not None:
        return pe
    if not all(kps[i][2] >= MIN_CONF for i in (L_SHOULDER, R_SHOULDER, L_HIP, R_HIP)):
        return None
    ombros = (kps[L_SHOULDER][:2] + kps[R_SHOULDER][:2]) / 2
    quadris = (kps[L_HIP][:2] + kps[R_HIP][:2]) / 2
    tronco = float(np.linalg.norm(ombros - quadris))
    return quadris + np.array([0.0, PERNA_TRONCOS * tronco]), "estimado"


class Trajeto:
    """Histórico do ponto no chão de um atleta, sempre nas coordenadas do quadro atual."""

    def __init__(self, fps: float) -> None:
        self.fps = fps
        self.janela = max(3, round(JANELA_S * fps))
        self.pts: deque[tuple[int, np.ndarray]] = deque()
        self.fonte: str | None = None
        self.altura: float | None = None   # EMA da altura do corpo na tela (px)

    def reset(self) -> None:
        self.pts.clear()
        self.fonte = None
        self.altura = None

    def transportar(self, M: np.ndarray) -> None:
        """Câmera andou: leva o histórico para as coordenadas do quadro novo."""
        A, t = M[:, :2], M[:, 2]
        self.pts = deque((f, A @ p + t) for f, p in self.pts)
        if self.altura is not None:
            self.altura *= float(np.sqrt(abs(np.linalg.det(A))))

    def adicionar(self, frame: int, ponto: np.ndarray, fonte: str, altura: float) -> None:
        if fonte != self.fonte:   # trocou tornozelo por quadril: pontos não comparáveis
            self.reset()
            self.fonte = fonte
        self.altura = altura if self.altura is None else 0.85 * self.altura + 0.15 * altura
        self.pts.append((frame, np.asarray(ponto, float)))
        while self.pts and self.pts[0][0] < frame - self.janela:
            self.pts.popleft()

    def velocidade(self, frame: int) -> np.ndarray | None:
        """Velocidade (corpos/s, eixos da tela) na janela, ou None sem histórico suficiente.

        Inclinação da reta de mínimos quadrados (posição × quadro): o tremor do keypoint
        nas pontas da janela pesa bem menos que em "último − primeiro".
        """
        if not self.pts or self.pts[-1][0] != frame or not self.altura:
            return None
        if len(self.pts) < MIN_JANELA * self.janela or frame - self.pts[0][0] < MIN_JANELA * self.janela:
            return None
        f = np.array([q for q, _ in self.pts], float)
        p = np.array([pt for _, pt in self.pts])
        f -= f.mean()
        inclinacao = (f @ (p - p.mean(axis=0))) / (f @ f)   # px/quadro, (x, y)
        v = inclinacao / self.altura * self.fps
        return None if float(np.linalg.norm(v)) > VEL_MAX else v


def decompor(vel: np.ndarray, eixo: np.ndarray, escorco: float) -> tuple[float, float, float]:
    """(velocidade, frente, esquerda) em corpos/s no chão. eixo = atleta → oponente na tela."""
    g = np.array([vel[0], vel[1] / escorco])
    u = np.array([eixo[0], eixo[1] / escorco])
    n = float(np.linalg.norm(u))
    if n < 1e-6:
        return float(np.linalg.norm(g)), 0.0, 0.0
    u /= n
    # tela com y para baixo vista de cima: girar u 90° no sentido anti-horário da tela
    # dá a esquerda de quem olha na direção u
    esquerda = np.array([u[1], -u[0]])
    return float(np.linalg.norm(g)), float(g @ u), float(g @ esquerda)


def rotular(vel: float, frente: float, esquerda: float) -> str:
    if vel < MIN_VEL:
        return "parado"
    if abs(frente) >= abs(esquerda):
        return "frente" if frente > 0 else "tras"
    return "esq" if esquerda > 0 else "dir"


def _moda(rotulos: list[str]) -> list[str]:
    meio = SUAVIZA // 2
    out = []
    for i in range(len(rotulos)):
        jan = rotulos[max(0, i - meio):i + meio + 1]
        out.append(max(set(jan), key=lambda r: (jan.count(r), r == rotulos[i])))
    return out


def resumir(registros: list[dict], fps: float, quadros: int, escorco: float = ESCORCO) -> dict:
    """Rótulo por quadro + totais por atleta.

    registros: [{"frame", "slot", "vx", "vy", "ex", "ey", "fonte", "fonte_opp"}], com
    (ex, ey) = separação até o oponente em alturas de corpo. Devolve
    {"escorco", "params", "atletas": {slot: {...}}} e grava em cada registro "vel",
    "frente", "esq", "rotulo".
    """

    atletas = {}
    for slot in sorted({r["slot"] for r in registros}):
        regs = sorted((r for r in registros if r["slot"] == slot), key=lambda r: r["frame"])
        brutos = []
        for r in regs:
            v, fr, esq = decompor(np.array([r["vx"], r["vy"]]), np.array([r["ex"], r["ey"]]), escorco)
            r.update(vel=round(v, 3), frente=round(fr, 3), esq=round(esq, 3))
            brutos.append(rotular(v, fr, esq))
        # suaviza só dentro de trechos contínuos (lacuna ≤ 2 quadros)
        rotulos: list[str] = []
        ini = 0
        for i in range(1, len(regs) + 1):
            if i == len(regs) or regs[i]["frame"] - regs[i - 1]["frame"] > 2:
                rotulos += _moda(brutos[ini:i])
                ini = i
        for r, rot in zip(regs, rotulos):
            r["rotulo"] = rot

        t = {k: 0 for k in ("parado",) + DIRECOES}
        n = {k: 0 for k in DIRECOES}
        dist = 0.0
        i = 0
        while i < len(regs):
            j = i
            while (j + 1 < len(regs) and rotulos[j + 1] == rotulos[i]
                   and regs[j + 1]["frame"] - regs[j]["frame"] <= 2):
                j += 1
            dur = (regs[j]["frame"] - regs[i]["frame"] + 1) / fps
            t[rotulos[i]] += dur
            if rotulos[i] in n and dur >= MIN_DURACAO_S:
                n[rotulos[i]] += 1
            i = j + 1
        for r in regs:
            if r["rotulo"] != "parado":
                dist += r["vel"] / fps
        medido = sum(t.values())
        atletas[slot] = {
            **{f"t_{k}": round(v, 1) for k, v in t.items()},
            **{f"n_{k}": v for k, v in n.items()},
            "t_medido": round(medido, 1),
            "medido_pct": round(100 * medido * fps / max(quadros, 1)),
            "distancia_corpos": round(dist, 1),
            # eixo com os pés do oponente estimados pelo quadril (oponente em plano cortado)
            "eixo_estimado_pct": round(100 * sum(r["fonte_opp"] == "estimado" for r in regs)
                                       / max(len(regs), 1)),
        }
    return {"escorco": escorco,
            "params": {"janela_s": JANELA_S, "min_vel": MIN_VEL, "vel_max": VEL_MAX,
                       "min_duracao_s": MIN_DURACAO_S, "razao_tronco": RAZAO_TRONCO},
            "atletas": atletas}
