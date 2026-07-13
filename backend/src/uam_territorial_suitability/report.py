"""Human-readable aptitude report, distinct from the raw JSON/interactive map.

The tool's functional scope (13-Camada2/CONTEXT.md) always included "mapas,
indicadores e relatórios" as three separate output types — the map and the
JSON exist since Gate G3, this module closes the third (flagged as an open
G3 pendency, see STATUS.md 2026-07-13).

Deliberately plain HTML (no template engine dependency): the browser's own
"print to PDF" turns this into a shareable document, and it stays trivial
to unit-test as a string.
"""

from datetime import datetime, timezone
from html import escape

from uam_territorial_suitability.api.routes import AptitudeRequest, AptitudeResponse
from uam_territorial_suitability.criteria import CRITERIA
from uam_territorial_suitability.site_type import SiteTypeResult

_CRITERIA_BY_ID = {c.id: c for c in CRITERIA}

_STATUS_LABELS = {
    "computed": "Computado",
    "not_implemented": "Não implementado (fonte de dado não configurada)",
    "failed": "Falhou (erro na computação)",
}


def _format_value(value: float | bool | None) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "Sim" if value else "Não"
    return f"{value:.3f}"


def render_aptitude_report_html(
    request: AptitudeRequest,
    response: AptitudeResponse,
    site_type: SiteTypeResult | None = None,
) -> str:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    site_type_block = ""
    if site_type is not None:
        elevated = (
            "elevado" if site_type.elevated is True
            else "solo" if site_type.elevated is False
            else "—"
        )
        site_type_block = f"""
      <tr><th>Tipo de sítio</th><td>{escape(site_type.site_type)} ({elevated})</td></tr>
      <tr><th>Registro ANAC</th><td>{escape(site_type.nome or "—")} ({escape(site_type.ciad or "—")})</td></tr>
"""

    criteria_rows = []
    for criterion_id, outcome in response.criteria.items():
        meta = _CRITERIA_BY_ID.get(criterion_id)
        name = meta.name if meta else criterion_id
        sources = ", ".join(meta.sources) if meta else "—"
        weight = f"{meta.weight:.3f}" if meta and meta.weight is not None else "—"
        status_label = _STATUS_LABELS.get(outcome.status.value, outcome.status.value)
        row_class = "computed" if outcome.status.value == "computed" else "pending"
        criteria_rows.append(f"""
      <tr class="{row_class}">
        <td>{escape(name)}</td>
        <td>{escape(status_label)}</td>
        <td>{_format_value(outcome.value)}</td>
        <td>{weight}</td>
        <td class="detail">{escape(outcome.detail or "—")}</td>
        <td class="sources">{escape(sources)}</td>
      </tr>""")

    if response.aptitude is not None:
        aptitude_block = f"""
    <p class="score">Score de aptidão (AHP): <strong>{response.aptitude:.3f}</strong>
      {"(sítio excluído por critério binário)" if response.excluded else ""}</p>"""
    else:
        aptitude_block = f"""
    <p class="score pending">Score final não calculado — {escape(response.note)}</p>"""

    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>Relatório de aptidão territorial — {request.latitude:.5f}, {request.longitude:.5f}</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Arial, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; }}
  h1 {{ font-size: 1.4rem; }}
  h2 {{ font-size: 1.05rem; margin-top: 2rem; border-bottom: 1px solid #ddd; padding-bottom: 0.25rem; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 0.75rem; }}
  th, td {{ text-align: left; padding: 0.4rem 0.5rem; border-bottom: 1px solid #eee; font-size: 0.85rem; vertical-align: top; }}
  tr.pending td {{ color: #888; }}
  td.detail, td.sources {{ font-size: 0.78rem; color: #555; }}
  .score {{ font-size: 1.1rem; margin-top: 1rem; }}
  .score.pending {{ color: #a05a00; font-size: 0.95rem; }}
  .meta table th {{ width: 220px; color: #555; font-weight: normal; }}
  footer {{ margin-top: 2.5rem; font-size: 0.75rem; color: #888; border-top: 1px solid #ddd; padding-top: 0.5rem; }}
  @media print {{ body {{ margin: 0; }} }}
</style>
</head>
<body>
  <h1>Relatório de aptidão territorial — Módulo 02 (UAM)</h1>
  <p>Gerado em {generated_at}</p>

  <h2>Sítio candidato</h2>
  <table class="meta">
    <tbody>
      <tr><th>Coordenadas (WGS84)</th><td>{request.latitude:.6f}, {request.longitude:.6f}</td></tr>
      <tr><th>Diâmetro disponível informado</th><td>{request.available_diameter_m:.1f} m</td></tr>
      <tr><th>Aeronave de referência (D)</th><td>{request.aircraft_d_m:.1f} m</td></tr>
      <tr><th>Norma de geometria</th><td>{escape(request.geometry_standard.value)}</td></tr>
      {site_type_block}
    </tbody>
  </table>

  <h2>Critérios de aptidão territorial</h2>
  <table>
    <thead>
      <tr><th>Critério</th><th>Status</th><th>Valor</th><th>Peso (AHP)</th><th>Detalhe</th><th>Fonte</th></tr>
    </thead>
    <tbody>{"".join(criteria_rows)}
    </tbody>
  </table>

  <h2>Resultado</h2>
  {aptitude_block}

  <footer>
    Módulo 02 — Aptidão Territorial (UAM Planning Framework). Metodologia completa:
    13-Camada2/04-metodologia/criterios_aptidao.md. Ferramenta open-source:
    github.com/marcelosrvperes/uam-territorial-suitability. Este relatório é gerado
    automaticamente a partir do cálculo em tempo real — não substitui verificação de
    engenharia antes de implantação.
  </footer>
</body>
</html>"""
