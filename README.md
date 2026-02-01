# Throxy Outbound Pipeline UI

A web UI + FastAPI backend for the Throxy outbound sales pipeline. It helps you funnel a raw list of people into a tight target audience using company stage, persona guidance, and step-by-step AI-powered prompts.

## Features

- Shadcn-inspired UI for stage selection, persona/profile editing, and prompt tuning
- Step-by-step pipeline that visually reduces the list size at each filtering gate
- Prompts stored in `data/prompts.md` and editable in the UI
- Final target list saved as a local CSV export
- Gemini AI integration for intelligent filtering
- PostgreSQL + pgvector for data persistence

---

## Running Locally

> **Note:** The Gemini API keys (`GOOGLE_API_KEY` / `GEMINI_API_KEY`) are provided automatically by the deployment platform. No manual configuration needed.

### Option 1: Docker Compose (Recommended)

This is the easiest way to run the full stack locally, including the database and all services.

```bash
# Start all services (backend, database, llama)
docker compose up --build

# Or run in detached mode
docker compose up --build -d
```

The app will be available at **http://localhost:8000**

To stop the services:
```bash
docker compose down
```

To stop and remove all data volumes:
```bash
docker compose down -v
```

### Option 2: Run Backend Directly (Python)

Use this option for faster iteration during development.

#### Prerequisites
- Python 3.11+
- PostgreSQL with pgvector extension (or use Docker for the database only)

#### 1. Start the database (if not using an external one)

```bash
docker compose up db -d
```

#### 2. Set up Python environment

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
```

#### 3. Configure environment variables

Create a `.env` file in the project root (or export these variables):

```bash
# Database connection
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/tomo

# Gemini settings (provided by deployment platform, but needed for local dev)
GEMINI_CLI_ENABLED=1
GEMINI_PIPELINE_ENABLED=1
GEMINI_CLI_COMMAND="gemini --output-format json --prompt"
```

#### 4. Run the backend

```bash
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000** to use the UI.

---

## Project Structure

```
├── backend/           # FastAPI backend
│   ├── main.py        # Application entry point
│   ├── pipeline.py    # Pipeline filtering logic
│   ├── gemini_client.py  # Gemini AI integration
│   └── ...
├── frontend/          # Static web UI
│   ├── index.html
│   └── main.js
├── data/              # Configuration and data files
│   ├── prompts.md     # Prompt templates for each filtering step
│   ├── persona.md     # Ideal customer persona
│   ├── company_profile.md  # Company targeting context
│   ├── sources.csv    # Input data sources
│   └── exports/       # Generated CSV exports
└── docker-compose.yml
```

## Customizing Templates

Edit these files to customize the pipeline behavior:

| File | Purpose |
|------|---------|
| `data/prompts.md` | Prompt text for each filtering step |
| `data/persona.md` | Ideal persona template and notes |
| `data/company_profile.md` | Company background and targeting context |

You can edit these files directly or through the UI.

---

## Running Tests

```bash
# Activate virtual environment first
source .venv/bin/activate

# Run all tests
pytest

# Run with verbose output
pytest -v
```

---

## Troubleshooting

### Database connection issues
- Ensure PostgreSQL is running: `docker compose up db -d`
- Check the connection string in `DATABASE_URL`

### Port already in use
- Change the port: `uvicorn backend.main:app --port 8001`
- Or stop conflicting services: `docker compose down`

### Gemini CLI not working
- Ensure `GEMINI_CLI_ENABLED=1` is set
- The Gemini CLI is installed automatically in the Docker container
- For local development without Docker, install it manually: `npm install -g @google/gemini-cli`
