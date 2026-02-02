"""FastAPI backend for Throxy outbound pipeline UI."""
import logging
import os
import traceback
from typing import Any, Dict, List
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .pipeline import run_pipeline, write_csv
from .profile_store import load_profiles, save_profiles
from .prompt_store import PromptStep, load_prompts, save_prompts
from .settings import EXPORT_DIR
from .gemini_cli import run_company_research, is_enabled as gemini_enabled, GeminiCLIError


logger = logging.getLogger("backend")


def _run_company_research_direct(prompt: str, context: Dict[str, Any], api_key: str) -> str:
    try:
        import google.generativeai as genai
    except Exception as exc:
        raise RuntimeError("google-generativeai is not available") from exc

    model_name = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)

    persona = context.get("persona") or ""
    full_prompt = (
        "Write a concise 200-300 word markdown company profile for Throxy. "
        "Include product summary, target audience notes, and competitive positioning. "
        "If you cannot browse, make reasonable assumptions and label them. "
        "Use headings and bullet points where helpful.\n\n"
        f"Persona context:\n{persona}"
    )

    response = model.generate_content(full_prompt)
    text = getattr(response, "text", None)
    if not text:
        raise RuntimeError("Gemini API returned no content")
    return text.strip()


class PromptPayload(BaseModel):
    step_id: str
    title: str
    prompt: str


class PromptsUpdateRequest(BaseModel):
    steps: List[PromptPayload]


class ProfileUpdateRequest(BaseModel):
    persona: str
    company: str


class CompanyPopulateRequest(BaseModel):
    persona: str = ""


class PipelineRequest(BaseModel):
    people: List[Dict[str, Any]]
    prompts: List[PromptPayload]


class PipelineStepResponse(BaseModel):
    step_id: str
    title: str
    prompt: str
    before_count: int
    after_count: int
    kept: List[Dict[str, Any]]
    removed: List[Dict[str, Any]]
    kept_justification: str
    removed_justification: str


class PipelineResponse(BaseModel):
    stage: str
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


@app.post("/api/company/auto")
def populate_company_profile(req: CompanyPopulateRequest) -> Dict[str, str]:
    context = {"persona": req.persona}
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=400, detail="Gemini API key missing in environment.")

    profile_md = None
    cli_error = None
    if gemini_enabled():
        base_prompt = (
            "Using chrome-dev-tools MCP, do a brief search of recent publications, funding news, press releases, or product updates about Throxy. "
            "Return a concise, 200-300 word markdown summary under company_profile_md. Include dates and source names when possible."
        )
        try:
            profile_md = run_company_research(base_prompt, context, api_key=api_key)
        except GeminiCLIError as exc:
            cli_error = exc

    if not profile_md:
        try:
            profile_md = _run_company_research_direct("", context, api_key=api_key)
        except Exception as exc:
            if cli_error:
                raise HTTPException(status_code=502, detail=f"Gemini CLI failed: {cli_error}; Gemini API failed: {exc}")
            raise HTTPException(status_code=502, detail=f"Gemini API failed: {exc}")

    return {"company": profile_md}


@app.post("/api/pipeline/run", response_model=PipelineResponse)
def run_pipeline_endpoint(req: PipelineRequest) -> PipelineResponse:
    profiles = load_profiles()
    prompt_steps = [PromptStep(step_id=step.step_id, title=step.title, prompt=step.prompt) for step in req.prompts]

    try:
        results, final_people, stage_label = run_pipeline(
            req.people,
            prompt_steps,
            profiles["persona"],
            profiles["company"],
        )
    except GeminiCLIError as exc:
        logger.error("Gemini pipeline failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Gemini pipeline failed: {exc}")
    except Exception as exc:  # pragma: no cover
        logger.error("Pipeline error: %s\n%s", exc, traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Pipeline error: {exc}")

    csv_path = write_csv(final_people)
    csv_filename = csv_path.name
    return PipelineResponse(
        stage=stage_label,
        steps=[
            PipelineStepResponse(
                step_id=result.step_id,
                title=result.title,
                prompt=result.prompt,
                before_count=result.before_count,
                after_count=result.after_count,
                kept=result.kept,
                removed=result.removed,
                kept_justification=result.kept_justification,
                removed_justification=result.removed_justification,
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
