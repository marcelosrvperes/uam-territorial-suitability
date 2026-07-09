"""Territorial aptitude criteria definitions.

Source of truth for the criteria themselves (justification, normative
references, formulas) is the thesis documentation, not this file:
    13-Camada2/04-metodologia/criterios_aptidao.md
    13-Camada2/04-metodologia/metodo_agregacao.md
(Google Drive, outside this repository — see README.md "Relação com a tese").

This module only mirrors the criteria as structured data for the API and
pipeline. Keep it in sync manually whenever the methodology changes.
"""

from enum import Enum

from pydantic import BaseModel


class CriterionKind(str, Enum):
    EXCLUSION = "exclusion"  # binary pass/fail filter, applied before weighting
    WEIGHTED = "weighted"  # continuous, enters the AHP aggregation


class Criterion(BaseModel):
    id: str
    name: str
    kind: CriterionKind
    weight: float | None = None  # only set for WEIGHTED criteria (proposal, see D29)
    sources: list[str]
    notes: str


CRITERIA: list[Criterion] = [
    Criterion(
        id="geometry",
        name="Geometria e dimensões mínimas",
        kind=CriterionKind.EXCLUSION,
        sources=["FAA EB-105A (2024)", "EASA PTS-VPT-DSN (2022)", "RBAC 155 EMD 01"],
        notes="FAA e EASA mantidos como normas configuráveis (D26), não uma escolha única.",
    ),
    Criterion(
        id="obstacles",
        name="Obstáculos físicos",
        kind=CriterionKind.WEIGHTED,
        weight=0.221,
        sources=["RBAC 154 / ICAO Annex 14 Vol I", "FAA EB-105A / EASA PTS-VPT-DSN (Obstacle-Free Volume)"],
        notes=(
            "RBAC 154/Anexo 14 para sítios que já são aeródromo certificado; "
            "OFV nativo FAA/EASA para os demais (D26)."
        ),
    ),
    Criterion(
        id="heliport_retrofit",
        name="Adequação de heliponto/aeródromo existente",
        kind=CriterionKind.EXCLUSION,
        sources=["Aplicação combinada dos critérios geometry + obstacles"],
        notes="Não é critério independente — reaproveita geometry/obstacles sobre a base ANAC/DECEA.",
    ),
    Criterion(
        id="land_use",
        name="Uso do solo e compatibilidade de vizinhança",
        kind=CriterionKind.WEIGHTED,
        weight=0.268,
        sources=["Ison, D. — WSDOT Vertiports Land Use Compatibility Supplement"],
        notes="Peso via proxy fraco (mapeamento de Mercan et al. 2025) — revisar (D29).",
    ),
    Criterion(
        id="proximity",
        name="Proximidade a infraestrutura",
        kind=CriterionKind.WEIGHTED,
        weight=0.047,
        sources=["Ison/WSDOT", "Wei et al. (2023) — Mineta Transportation Institute"],
        notes="Divergência Wei vs. Ison sobre infraestrutura elétrica ainda não reconciliada.",
    ),
    Criterion(
        id="airspace_light",
        name="Compatibilidade aeroespacial leve",
        kind=CriterionKind.WEIGHTED,
        weight=0.464,
        sources=["Rede REH (DECEA/GeoAISWEB)"],
        notes=(
            "Peso alto não contradiz ser 'leve' — profundidade de cálculo (binário/proximidade) "
            "e peso na agregação são eixos independentes (ver DECISIONS.md D29/D30)."
        ),
    ),
    Criterion(
        id="topography",
        name="Topografia / declividade",
        kind=CriterionKind.EXCLUSION,
        sources=["ICAO Annex 14 Vol II — Heliports"],
        notes="FATO ≤3% geral, ≤2% heliponto elevado (analogia heliponto→vertiporto).",
    ),
]
