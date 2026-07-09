# UAM Territorial Suitability — Backend

FastAPI backend for the territorial aptitude tool (Módulo 02 of the UAM Planning Framework
thesis). See the repository root `README.md` for the full picture.

## Setup

```bash
python -m venv .venv
./.venv/Scripts/activate   # or source .venv/bin/activate on Linux/macOS
pip install -e ".[dev]"
```

## Run

```bash
uvicorn uam_territorial_suitability.main:app --reload
```

## Test

```bash
pytest
```
