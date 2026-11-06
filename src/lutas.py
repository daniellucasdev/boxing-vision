"""Lutas completas já processadas pelo pipeline e que estão na base MHdS.

Fonte única para a avaliação da E5 (avaliar_estados.py), a de golpes (avaliar_golpes.py) e a
revisão rápida de golpes na web (/golpes). Início de cada round em segundos do vídeo, conferido
no placar (quadro ÷ fps). Para incluir uma luta: rodar o pipeline com a saída em
outputs/lutas/<nome>/ e acrescentar aqui.
"""

from __future__ import annotations

LUTAS = [
    {"nome": "pan2023_final_92kg_lacruz_x_keno", "luta_id": "94",
     "inicios": [1470 / 30, 8675 / 30, 15880 / 30]},
    {"nome": "pan2023_semi_92mais_edwards_x_arzola", "luta_id": "92",
     "inicios": [4593 / 29.97, 11791 / 29.97, 19111 / 29.97]},
]
DURACAO_ROUND_S = 180.0


def pasta(luta: dict) -> str:
    """Saída do pipeline, relativa ao repositório."""
    return f"outputs/lutas/{luta['nome']}"


def video(luta: dict) -> str:
    """Vídeo relativo a data/ (como o modo juiz espera)."""
    return f"lutas/{luta['nome']}.mp4"


def por_nome(nome: str) -> dict | None:
    return next((l for l in LUTAS if l["nome"] == nome), None)


def round_de(luta: dict, t: float) -> int | None:
    """Round (1, 2, 3) do instante t do vídeo, ou None se fora dos rounds."""
    for i, ini in enumerate(luta["inicios"], start=1):
        if ini <= t < ini + DURACAO_ROUND_S:
            return i
    return None
