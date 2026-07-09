# UAM Territorial Suitability

Ferramenta computacional de aptidão territorial para infraestrutura de Mobilidade Aérea Urbana
(UAM) — Módulo 02 do *UAM Planning Framework*, tese de doutorado (ITA).

Dado um conjunto de dados geoespaciais fornecido por um gestor público, a ferramenta valida os
dados, aplica critérios científicos de aptidão territorial (geometria, obstáculos, uso do solo,
proximidade a infraestrutura, compatibilidade aeroespacial leve, topografia) e produz mapas,
indicadores e relatórios — incluindo a avaliação de helipontos/aeródromos existentes para
reaproveitamento como vertiportos. Caso piloto de validação: Região Metropolitana de São Paulo
(RMSP).

## Relação com a tese

Este repositório é só o **código**. A metodologia, as decisões de escopo, a justificativa
normativa de cada critério e o histórico de decisões vivem na pasta do módulo na tese (Google
Drive, fora deste repositório):

```
13-Camada2/                        (Módulo 02 — Aptidão Territorial)
├── 04-metodologia/
│   ├── criterios_aptidao.md       ← definição e fonte de cada critério
│   └── metodo_agregacao.md        ← método AHP e matriz de pesos
├── DECISIONS.md                   ← registro de decisões (D01–D30+)
└── GOVERNANCE.md                  ← Stage Gates do módulo
```

Sempre que a metodologia mudar, atualizar lá primeiro — este código é a implementação dessa
metodologia, não a fonte dela.

## Arquitetura

```
backend/    FastAPI + geopandas/rasterio — validação de dados, cálculo de aptidão, API REST
frontend/   Next.js — interface para o gestor público (upload de dados, mapa, indicadores)
```

Dados geoespaciais brutos (grandes) **não** ficam neste repositório — são fornecidos pelo usuário
em tempo de execução ou referenciados externamente.

## Setup

### Backend

```bash
cd backend
python -m venv .venv
./.venv/Scripts/activate   # Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
uvicorn uam_territorial_suitability.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend em `http://localhost:3000`, backend em `http://localhost:8000`.

## Status

Protótipo inicial (Gate G3 em andamento) — API expõe os critérios definidos na metodologia
(`GET /api/criteria`); o pipeline de cálculo de aptidão (`POST /api/aptitude`) ainda não está
implementado.

## Licença

MIT — ver `LICENSE`.
