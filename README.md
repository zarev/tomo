# Throxy Outbound Pipeline UI

This repo now ships a simple web UI + FastAPI backend for the Throxy outbound pipeline. It helps you funnel a raw list of people into a tight target audience using company stage, persona guidance, and step-by-step prompts (stored in markdown files).

## Features
- Shadcn-inspired UI for stage selection, persona/profile editing, and prompt tuning.
- Step-by-step pipeline that visually reduces the list size at each gate.
- Prompts stored in `data/prompts.md` and editable in the UI.
- Final target list saved as a local CSV export.
- Optional Gemini CLI integration with MCP web search (`chrome-dev-tools`).

## Local development

### 1) Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

### 2) Run the app

```bash
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000 to use the UI.

### 3) Update prompt and profile templates

- `data/prompts.md` — prompt text for each filtering step.
- `data/persona.md` — ideal persona template and notes.
- `data/company_profile.md` — company background and targeting notes.

You can edit these files directly or save them from the UI.

## Gemini CLI + MCP integration

The backend can call Gemini CLI when `GEMINI_CLI_ENABLED=1`.

```bash
export GEMINI_CLI_ENABLED=1
export GEMINI_CLI_COMMAND="gemini --mcp chrome-dev-tools --json"
```

The pipeline will send each step prompt + data as JSON via stdin and expects a JSON response containing `keep_indices` (array of indices to keep). If Gemini CLI is not enabled, the app falls back to heuristic filtering.

## Docker deployment

Build and run a simple container:

```bash
docker build -t throxy-pipeline .
docker run -p 8000:8000 throxy-pipeline
```

Then open http://localhost:8000.

## Tests

```bash
pytest
```
