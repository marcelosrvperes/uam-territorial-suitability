"use client";

import { useState } from "react";
import { MapContainer, TileLayer, Marker, Popup, useMapEvents } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

// Leaflet's default marker icons reference image paths that don't resolve
// under Next.js's bundler — point them at the files leaflet ships instead.
delete (L.Icon.Default.prototype as unknown as { _getIconUrl?: unknown })._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Metropolitan Region of São Paulo, roughly centered — pilot case (D07).
const RMSP_CENTER: [number, number] = [-23.5613, -46.6565];

type CriterionOutcome = {
  status: "computed" | "not_implemented" | "failed";
  value: number | boolean | null;
  detail: string | null;
};

type AptitudeResponse = {
  criteria: Record<string, CriterionOutcome>;
  aptitude: number | null;
  excluded: boolean | null;
  note: string;
};

// Mirrors backend SiteTypeResult (site_type.py, D55).
type SiteTypeResponse = {
  site_type: "heliponto" | "aerodromo" | "sem_registro";
  ciad: string | null;
  nome: string | null;
  elevacao_m: number | null;
  elevated: boolean | null;
  in_scope: boolean;
  note: string;
};

type MarkerState = {
  lat: number;
  lon: number;
  siteType: SiteTypeResponse | null;
  result: AptitudeResponse | null;
  referenceElevationM: number | null;
  loading: boolean;
  error: string | null;
};

function ClickHandler({ onClick }: { onClick: (lat: number, lon: number) => void }) {
  useMapEvents({
    click(e) {
      onClick(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

async function fetchSiteType(lat: number, lon: number): Promise<SiteTypeResponse> {
  const params = new URLSearchParams({ latitude: String(lat), longitude: String(lon) });
  const response = await fetch(`${API_URL}/api/site-type?${params}`);
  if (!response.ok) {
    throw new Error(`API respondeu ${response.status}`);
  }
  return response.json();
}

// Mirrors the body sent to POST /api/aptitude — kept in one place so the
// "Ver relatório" link (GET /api/aptitude/report) always requests the exact
// same computation the user already saw on screen.
function aptitudeParams(lat: number, lon: number, referenceElevationM: number) {
  return {
    latitude: lat,
    longitude: lon,
    available_diameter_m: 40.0,
    aircraft_d_m: 16.0,
    geometry_standard: "easa",
    reference_elevation_m: referenceElevationM,
  };
}

async function computeAptitude(
  lat: number,
  lon: number,
  referenceElevationM: number,
): Promise<AptitudeResponse> {
  const response = await fetch(`${API_URL}/api/aptitude`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(aptitudeParams(lat, lon, referenceElevationM)),
  });
  if (!response.ok) {
    throw new Error(`API respondeu ${response.status}`);
  }
  return response.json();
}

function reportUrl(lat: number, lon: number, referenceElevationM: number): string {
  const params = aptitudeParams(lat, lon, referenceElevationM);
  const query = new URLSearchParams(
    Object.fromEntries(Object.entries(params).map(([k, v]) => [k, String(v)])),
  );
  return `${API_URL}/api/aptitude/report?${query}`;
}

// Placeholder used only when the site has no ANAC record (laje/proposta nova)
// to draw its own ground elevation from — no real source wired up yet.
const FALLBACK_REFERENCE_ELEVATION_M = 760.0;

const CRITERION_LABELS: Record<string, string> = {
  geometry: "Geometria",
  airspace_light: "Compatibilidade aeroespacial",
  obstacles: "Obstáculos físicos",
  land_use: "Uso do solo",
  proximity: "Proximidade a infraestrutura",
  heliport_retrofit: "Adequação de heliponto",
};

const SITE_TYPE_LABELS: Record<SiteTypeResponse["site_type"], string> = {
  heliponto: "Heliponto existente",
  aerodromo: "Aeródromo certificado",
  sem_registro: "Sem registro ANAC",
};

function SiteTypePanel({ siteType }: { siteType: SiteTypeResponse }) {
  const label = SITE_TYPE_LABELS[siteType.site_type];
  const suffix =
    siteType.site_type === "heliponto"
      ? siteType.elevated === true
        ? " (elevado)"
        : siteType.elevated === false
          ? " (solo)"
          : ""
      : "";
  return (
    <div
      style={{
        background: siteType.in_scope ? "#eef6ee" : "#f6efe0",
        border: `1px solid ${siteType.in_scope ? "#bcd9bc" : "#e0c98c"}`,
        borderRadius: 4,
        padding: "0.6rem 0.75rem",
        marginBottom: "0.75rem",
        fontSize: "0.85rem",
      }}
    >
      <strong>
        {label}
        {suffix}
      </strong>
      {siteType.nome && <div>{siteType.nome} {siteType.ciad ? `(${siteType.ciad})` : ""}</div>}
      <div style={{ color: "#555", marginTop: "0.25rem" }}>{siteType.note}</div>
    </div>
  );
}

function ResultPanel({ marker }: { marker: MarkerState }) {
  if (marker.error) return <p style={{ color: "#b00" }}>Erro: {marker.error}</p>;
  if (!marker.siteType) return <p>Identificando o sítio…</p>;

  return (
    <div style={{ fontSize: "0.9rem" }}>
      <SiteTypePanel siteType={marker.siteType} />
      {!marker.siteType.in_scope && (
        <p style={{ color: "#555" }}>
          Este módulo não calcula aptidão para aeródromo certificado — ver Módulo 03 (Zonas de
          Proteção).
        </p>
      )}
      {marker.siteType.in_scope && marker.loading && <p>Calculando aptidão…</p>}
      {marker.siteType.in_scope && marker.result && (
        <>
          <p style={{ margin: "0 0 0.5rem" }}>
            <strong>{marker.result.note}</strong>
          </p>
          {marker.result.aptitude !== null && (
            <p>
              Score de aptidão: <strong>{marker.result.aptitude.toFixed(3)}</strong>
              {marker.result.excluded ? " (excluído)" : ""}
            </p>
          )}
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <tbody>
              {Object.entries(marker.result.criteria).map(([id, outcome]) => (
                <tr key={id}>
                  <td style={{ padding: "2px 4px" }}>{CRITERION_LABELS[id] ?? id}</td>
                  <td style={{ padding: "2px 4px", color: outcome.status === "computed" ? "#080" : "#888" }}>
                    {outcome.status === "computed"
                      ? typeof outcome.value === "number"
                        ? outcome.value.toFixed(2)
                        : String(outcome.value)
                      : outcome.status}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {marker.referenceElevationM !== null && (
            <p style={{ marginTop: "0.75rem" }}>
              <a
                href={reportUrl(marker.lat, marker.lon, marker.referenceElevationM)}
                target="_blank"
                rel="noopener noreferrer"
              >
                Ver relatório completo ↗
              </a>
            </p>
          )}
        </>
      )}
    </div>
  );
}

export default function AptitudeMap() {
  const [marker, setMarker] = useState<MarkerState | null>(null);

  async function handleMapClick(lat: number, lon: number) {
    setMarker({ lat, lon, siteType: null, result: null, referenceElevationM: null, loading: true, error: null });
    try {
      const siteType = await fetchSiteType(lat, lon);
      setMarker({
        lat, lon, siteType, result: null, referenceElevationM: null,
        loading: siteType.in_scope, error: null,
      });

      if (!siteType.in_scope) return; // aeródromo certificado — Módulo 03, não este

      const referenceElevationM = siteType.elevacao_m ?? FALLBACK_REFERENCE_ELEVATION_M;
      const result = await computeAptitude(lat, lon, referenceElevationM);
      setMarker({ lat, lon, siteType, result, referenceElevationM, loading: false, error: null });
    } catch (err) {
      setMarker((prev) => ({
        lat, lon, siteType: prev?.siteType ?? null, result: null,
        referenceElevationM: prev?.referenceElevationM ?? null, loading: false,
        error: err instanceof Error ? err.message : String(err),
      }));
    }
  }

  return (
    <div style={{ display: "flex", gap: "1rem", height: "70vh" }}>
      <div style={{ flex: 2 }}>
        <MapContainer center={RMSP_CENTER} zoom={11} style={{ height: "100%", width: "100%" }}>
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <ClickHandler onClick={handleMapClick} />
          {marker && (
            <Marker position={[marker.lat, marker.lon]}>
              <Popup>
                {marker.lat.toFixed(5)}, {marker.lon.toFixed(5)}
              </Popup>
            </Marker>
          )}
        </MapContainer>
      </div>
      <div style={{ flex: 1, overflowY: "auto", borderLeft: "1px solid #ddd", paddingLeft: "1rem" }}>
        <h2 style={{ fontSize: "1.1rem" }}>Sítio candidato</h2>
        {!marker && <p>Clique no mapa para avaliar um sítio candidato.</p>}
        {marker && <ResultPanel marker={marker} />}
      </div>
    </div>
  );
}
