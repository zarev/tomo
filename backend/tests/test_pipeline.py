from pathlib import Path

from fastapi.testclient import TestClient


def test_pipeline_run(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    (tmp_path / "exports").mkdir(parents=True, exist_ok=True)

    from backend.prompt_store import PromptStep, save_prompts

    save_prompts(
        [
            PromptStep(step_id="stage-fit", title="Stage Fit Gate", prompt="Stage fit prompt"),
            PromptStep(step_id="persona-fit", title="Persona Fit", prompt="Persona fit prompt"),
            PromptStep(step_id="company-fit", title="Company Fit", prompt="Company fit prompt"),
            PromptStep(step_id="final-review", title="Final Review", prompt="Final review prompt"),
        ],
        tmp_path / "prompts.md",
    )
    (tmp_path / "persona.md").write_text("Persona details", encoding="utf-8")
    (tmp_path / "company_profile.md").write_text("Company details", encoding="utf-8")

    from backend.main import app

    client = TestClient(app)
    payload = {
        "people": [
            {"name": "Ava", "title": "Founder", "company": "StartCo", "email": "a@co.com"},
            {"name": "Ben", "title": "Engineer", "company": "BigCorp", "email": "b@co.com"},
        ],
        "stage": "pre-seed",
        "prompts": [
            {"step_id": "stage-fit", "title": "Stage Fit Gate", "prompt": "Stage fit prompt"},
            {"step_id": "persona-fit", "title": "Persona Fit", "prompt": "Persona fit prompt"},
            {"step_id": "company-fit", "title": "Company Fit", "prompt": "Company fit prompt"},
            {"step_id": "final-review", "title": "Final Review", "prompt": "Final review prompt"},
        ],
    }

    response = client.post("/api/pipeline/run", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "steps" in data
    assert "final_people" in data
    assert data["csv_download_url"].startswith("/api/exports/")
    export_path = Path(data["csv_path"])
    assert export_path.exists()
    assert export_path.read_text(encoding="utf-8").startswith("name,title")


def test_prompts_endpoint(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))

    from backend.prompt_store import PromptStep, save_prompts

    save_prompts(
        [
            PromptStep(step_id="stage-fit", title="Stage Fit Gate", prompt="Stage fit prompt"),
        ],
        tmp_path / "prompts.md",
    )

    from backend.main import app

    client = TestClient(app)
    response = client.get("/api/prompts")
    assert response.status_code == 200
    payload = response.json()
    assert payload["steps"][0]["step_id"] == "stage-fit"
