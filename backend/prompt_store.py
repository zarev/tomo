import re
from dataclasses import dataclass
from pathlib import Path
from typing import List

from .settings import PROMPTS_PATH

SECTION_RE = re.compile(r"^##\s+([a-z0-9_-]+)\s*:\s*(.+)$", re.IGNORECASE)


@dataclass
class PromptStep:
    step_id: str
    title: str
    prompt: str


DEFAULT_PROMPTS = [
    PromptStep(
        step_id="stage-fit",
        title="Stage Fit Gate",
        prompt=(
            "Use the company stage to narrow the list to the best initial buyers. "
            "Focus on decision-makers and teams who feel the pain of outbound infrastructure early."
        ),
    ),
    PromptStep(
        step_id="persona-fit",
        title="Persona Fit Filter",
        prompt=(
            "Use the ideal persona description to keep only leads who match the target roles, "
            "responsibilities, and pain points."
        ),
    ),
    PromptStep(
        step_id="company-fit",
        title="Throxy Value Alignment",
        prompt=(
            "Use Throxy's company profile to confirm industry, motion, and value alignment. "
            "Keep the smallest, highest intent audience."
        ),
    ),
    PromptStep(
        step_id="final-review",
        title="Final Target Review",
        prompt=(
            "Make a final pass to ensure the remaining list is laser-focused and ready for outreach."
        ),
    ),
]


def ensure_prompts_file(path: Path = PROMPTS_PATH) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    save_prompts(DEFAULT_PROMPTS, path)


def load_prompts(path: Path = PROMPTS_PATH) -> List[PromptStep]:
    ensure_prompts_file(path)
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()
    steps: List[PromptStep] = []
    current = None
    buffer: List[str] = []

    def flush() -> None:
        nonlocal buffer, current, steps
        if current is None:
            buffer = []
            return
        prompt_text = "\n".join(buffer).strip()
        steps.append(PromptStep(step_id=current[0], title=current[1], prompt=prompt_text))
        buffer = []

    for line in lines:
        match = SECTION_RE.match(line.strip())
        if match:
            flush()
            step_id, title = match.group(1).strip(), match.group(2).strip()
            current = (step_id, title)
            continue
        if current is not None:
            buffer.append(line)

    flush()

    if not steps:
        return DEFAULT_PROMPTS
    return steps


def save_prompts(steps: List[PromptStep], path: Path = PROMPTS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    chunks = ["# Throxy Outbound Pipeline Prompts", ""]
    for step in steps:
        chunks.append(f"## {step.step_id}: {step.title}")
        chunks.append(step.prompt.strip())
        chunks.append("")
    path.write_text("\n".join(chunks).strip() + "\n", encoding="utf-8")
