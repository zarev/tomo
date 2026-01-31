import csv
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .gemini_cli import GeminiCLIError, run_filter
from .prompt_store import PromptStep
from .settings import EXPORT_DIR

WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z-]{2,}")

STAGE_KEYWORDS = {
    "pre-seed": [
        "founder",
        "cofounder",
        "co-founder",
        "ceo",
        "cto",
        "head of growth",
        "growth",
        "revenue",
        "sales",
        "go-to-market",
        "operations",
        "product",
    ],
    "seed": [
        "vp sales",
        "vp growth",
        "head of sales",
        "marketing",
        "revenue operations",
        "sales ops",
    ],
}


@dataclass
class StepResult:
    step_id: str
    title: str
    prompt: str
    before_count: int
    after_count: int
    kept: List[Dict[str, Any]]
    removed: List[Dict[str, Any]]


def _extract_keywords(text: str) -> List[str]:
    words = [match.group(0).lower() for match in WORD_RE.finditer(text)]
    return sorted(set(words))


def _score_person(person: Dict[str, Any], keywords: List[str]) -> int:
    haystack = " ".join(
        str(person.get(key, ""))
        for key in ("name", "title", "company", "notes", "location", "industry")
    ).lower()
    return sum(1 for keyword in keywords if keyword in haystack)


def _filter_by_keywords(people: List[Dict[str, Any]], keywords: List[str], min_hits: int = 1) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    kept = []
    removed = []
    for person in people:
        score = _score_person(person, keywords)
        if score >= min_hits:
            kept.append(person)
        else:
            removed.append(person)
    return kept, removed


def _fallback_reduction(people: List[Dict[str, Any]], ratio: float) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    if not people:
        return [], []
    keep_count = max(1, int(len(people) * ratio))
    kept = people[:keep_count]
    removed = people[keep_count:]
    return kept, removed


def _apply_step(
    people: List[Dict[str, Any]],
    prompt: str,
    step_id: str,
    title: str,
    context: Dict[str, Any],
    fallback_keywords: List[str],
    fallback_ratio: float,
) -> StepResult:
    before_count = len(people)
    kept: List[Dict[str, Any]]
    removed: List[Dict[str, Any]]

    try:
        keep_indices = run_filter(prompt, people, context)
    except GeminiCLIError:
        keep_indices = None

    if keep_indices is not None:
        kept = [people[i] for i in keep_indices if 0 <= i < len(people)]
        removed = [person for idx, person in enumerate(people) if idx not in keep_indices]
    else:
        kept, removed = _filter_by_keywords(people, fallback_keywords)
        if not kept and people:
            kept, removed = _fallback_reduction(people, fallback_ratio)

    return StepResult(
        step_id=step_id,
        title=title,
        prompt=prompt,
        before_count=before_count,
        after_count=len(kept),
        kept=kept,
        removed=removed,
    )


def run_pipeline(
    people: List[Dict[str, Any]],
    stage: str,
    prompts: List[PromptStep],
    persona: str,
    company: str,
) -> Tuple[List[StepResult], List[Dict[str, Any]]]:
    stage = stage.lower().strip()
    stage_keywords = STAGE_KEYWORDS.get(stage, STAGE_KEYWORDS["pre-seed"])
    persona_keywords = _extract_keywords(persona)
    company_keywords = _extract_keywords(company)

    prompt_lookup = {step.step_id: step for step in prompts}
    ordered_steps = [
        ("stage-fit", "Stage Fit Gate", stage_keywords, 0.7),
        ("persona-fit", "Persona Fit Filter", persona_keywords, 0.6),
        ("company-fit", "Throxy Value Alignment", company_keywords, 0.6),
        ("final-review", "Final Target Review", persona_keywords + company_keywords, 0.5),
    ]

    results: List[StepResult] = []
    current_people = list(people)

    for step_id, default_title, fallback_keywords, ratio in ordered_steps:
        prompt_step = prompt_lookup.get(step_id)
        prompt_text = prompt_step.prompt if prompt_step else ""
        title = prompt_step.title if prompt_step else default_title
        context = {
            "stage": stage,
            "persona": persona,
            "company": company,
            "step_id": step_id,
        }
        result = _apply_step(
            current_people,
            prompt_text,
            step_id,
            title,
            context,
            fallback_keywords,
            ratio,
        )
        results.append(result)
        current_people = result.kept

    return results, current_people


def write_csv(people: List[Dict[str, Any]], export_dir: Path = EXPORT_DIR) -> Path:
    export_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    filename = f"throxy_targets_{timestamp}.csv"
    path = export_dir / filename

    fieldnames = ["name", "title", "company", "email", "location", "industry", "notes"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for person in people:
            writer.writerow({field: person.get(field, "") for field in fieldnames})

    return path
