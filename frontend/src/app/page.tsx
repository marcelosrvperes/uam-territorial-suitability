import AptitudeMapClient from "@/components/AptitudeMapClient";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Criterion = {
  id: string;
  name: string;
  kind: "exclusion" | "weighted";
  weight: number | null;
  sources: string[];
  notes: string;
};

async function getCriteria(): Promise<Criterion[] | null> {
  try {
    const res = await fetch(`${API_URL}/api/criteria`, { cache: "no-store" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

const cellStyle: React.CSSProperties = {
  border: "1px solid #ddd",
  padding: "0.5rem",
  textAlign: "left",
};

export default async function Home() {
  const criteria = await getCriteria();

  return (
    <main style={{ maxWidth: 1100, margin: "0 auto", padding: "2rem", fontFamily: "sans-serif" }}>
      <h1>UAM Territorial Suitability</h1>
      <p>Módulo 02 — ferramenta de aptidão territorial para vertiportos (protótipo inicial).</p>

      <AptitudeMapClient />

      <h2 style={{ marginTop: "2rem" }}>Critérios definidos</h2>
      {!criteria && (
        <p style={{ color: "#b00" }}>
          Não foi possível carregar os critérios de {API_URL}. O backend está rodando?
          (<code>uvicorn uam_territorial_suitability.main:app --reload</code>)
        </p>
      )}

      {criteria && (
        <table style={{ borderCollapse: "collapse", width: "100%" }}>
          <thead>
            <tr>
              <th style={cellStyle}>Critério</th>
              <th style={cellStyle}>Tipo</th>
              <th style={cellStyle}>Peso</th>
            </tr>
          </thead>
          <tbody>
            {criteria.map((c) => (
              <tr key={c.id}>
                <td style={cellStyle}>{c.name}</td>
                <td style={cellStyle}>{c.kind === "exclusion" ? "Exclusão" : "Ponderado"}</td>
                <td style={cellStyle}>{c.weight ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  );
}
