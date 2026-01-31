"""FastAPI backend for Throxy outbound pipeline UI."""
import os
from typing import Any, Dict, List
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .pipeline import run_pipeline, write_csv
from .profile_store import load_profiles, save_profiles
from .prompt_store import PromptStep, load_prompts, save_prompts
from .settings import EXPORT_DIR


class PromptPayload(BaseModel):
    step_id: str
    title: str
    prompt: str


class PromptsUpdateRequest(BaseModel):
    steps: List[PromptPayload]


class ProfileUpdateRequest(BaseModel):
    persona: str
    company: str


class PipelineRequest(BaseModel):
    people: List[Dict[str, Any]]
    stage: str
    prompts: List[PromptPayload]


class PipelineStepResponse(BaseModel):
    step_id: str
    title: str
    prompt: str
    before_count: int
    after_count: int
    kept: List[Dict[str, Any]]
    removed: List[Dict[str, Any]]


class PipelineResponse(BaseModel):
    steps: List[PipelineStepResponse]
    final_people: List[Dict[str, Any]]
    csv_path: str
    csv_download_url: str


app = FastAPI(title="throxy-outbound-pipeline")

frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if os.path.isdir(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="frontend_static")

    @app.get("/", include_in_schema=False)
    def root_index():
        index = os.path.join(frontend_dir, "index.html")
        if os.path.isfile(index):
            return FileResponse(index, media_type="text/html")
        raise HTTPException(status_code=404, detail="Index not found")


@app.get("/api/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/api/prompts")
def prompts() -> Dict[str, List[PromptPayload]]:
    steps = load_prompts()
    return {
        "steps": [
            PromptPayload(step_id=step.step_id, title=step.title, prompt=step.prompt)
            for step in steps
        ]
    }


@app.put("/api/prompts")
def update_prompts(req: PromptsUpdateRequest) -> Dict[str, str]:
    steps = [PromptStep(step_id=step.step_id, title=step.title, prompt=step.prompt) for step in req.steps]
    save_prompts(steps)
    return {"status": "saved"}


@app.get("/api/profile")
def profile() -> Dict[str, str]:
    return load_profiles()


@app.put("/api/profile")
def update_profile(req: ProfileUpdateRequest) -> Dict[str, str]:
    save_profiles(req.persona, req.company)
    return {"status": "saved"}


@app.post("/api/pipeline/run", response_model=PipelineResponse)
def run_pipeline_endpoint(req: PipelineRequest) -> PipelineResponse:
    profiles = load_profiles()
    prompt_steps = [PromptStep(step_id=step.step_id, title=step.title, prompt=step.prompt) for step in req.prompts]
    results, final_people = run_pipeline(req.people, req.stage, prompt_steps, profiles["persona"], profiles["company"])
    csv_path = write_csv(final_people)
    csv_filename = csv_path.name
    return PipelineResponse(
        steps=[
            PipelineStepResponse(
                step_id=result.step_id,
                title=result.title,
                prompt=result.prompt,
                before_count=result.before_count,
                after_count=result.after_count,
                kept=result.kept,
                removed=result.removed,
            )
            for result in results
        ],
        final_people=final_people,
        csv_path=str(csv_path),
        csv_download_url=f"/api/exports/{csv_filename}",
    )


@app.get("/api/exports/{filename}")
def download_export(filename: str) -> FileResponse:
    path = EXPORT_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Export not found")
    return FileResponse(path, media_type="text/csv", filename=filename)
