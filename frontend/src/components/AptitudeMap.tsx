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

type MarkerState = {
  lat: number;
  lon: number;
  result: AptitudeResponse | null;
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

async function computeAptitude(lat: number, lon: number): Promise<AptitudeResponse> {
  const response = await fetch(`${API_URL}/api/aptitude`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      latitude: lat,
      longitude: lon,
      available_diameter_m: 40.0,
      aircraft_d_m: 16.0,
      geometry_standard: "easa",
      reference_elevation_m: 760.0,
    }),
  });
  if (!response.ok) {
    throw new Error(`API respondeu ${response.status}`);
  }
  return response.json();
}

const CRITERION_LABELS: Record<string, string> = {
  geometry: "Geometria",
  airspace_light: "Compatibilidade aeroespacial",
  topography: "Topografia",
  obstacles: "Obstáculos físicos",
  land_use: "Uso do solo",
  proximity: "Proximidade a infraestrutura",
  heliport_retrofit: "Adequação de heliponto",
};

function ResultPanel({ marker }: { marker: MarkerState }) {
  if (marker.loading) return <p>Calculando…</p>;
  if (marker.error) return <p style={{ color: "#b00" }}>Erro: {marker.error}</p>;
  if (!marker.result) return null;

  return (
    <div style={{ fontSize: "0.9rem" }}>
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
    </div>
  );
}

export default function AptitudeMap() {
  const [marker, setMarker] = useState<MarkerState | null>(null);

  async function handleMapClick(lat: number, lon: number) {
    setMarker({ lat, lon, result: null, loading: true, error: null });
    try {
      const result = await computeAptitude(lat, lon);
      setMarker({ lat, lon, result, loading: false, error: null });
    } catch (err) {
      setMarker({
        lat, lon, result: null, loading: false,
        error: err instanceof Error ? err.message : String(err),
      });
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
