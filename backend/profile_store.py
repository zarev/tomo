from pathlib import Path

from .settings import COMPANY_PATH, PERSONA_PATH

DEFAULT_PERSONA = """# Ideal Persona (Template)

## Summary
Describe the ideal persona for Throxy's outbound pipeline here.

## General Pointers
- Role and seniority
- Company size and stage
- Pain points and current tooling
- Buying signals

## Detailed Pointers
- Specific job titles and teams
- Trigger events that indicate readiness
- Language and vocabulary they use
- Key objections to address
"""

DEFAULT_COMPANY = """# Throxy Company Profile (Template)

## Company Stage
Pre-seed, recently raised $6M.

## Product
Describe the outbound pipeline product, core workflow, and key differentiators.

## Target Audience Notes
- Industries to prioritize
- Company size or revenue range
- Regions and time zones
- Decision-maker characteristics

## Competitive Positioning
- Alternatives buyers are using today
- Why Throxy wins
"""


def ensure_profile_files() -> None:
    if not PERSONA_PATH.exists():
        PERSONA_PATH.parent.mkdir(parents=True, exist_ok=True)
        PERSONA_PATH.write_text(DEFAULT_PERSONA, encoding="utf-8")
    if not COMPANY_PATH.exists():
        COMPANY_PATH.parent.mkdir(parents=True, exist_ok=True)
        COMPANY_PATH.write_text(DEFAULT_COMPANY, encoding="utf-8")


def load_profiles() -> dict:
    ensure_profile_files()
    return {
        "persona": PERSONA_PATH.read_text(encoding="utf-8"),
        "company": COMPANY_PATH.read_text(encoding="utf-8"),
    }


def save_profiles(persona: str, company: str) -> None:
    PERSONA_PATH.parent.mkdir(parents=True, exist_ok=True)
    COMPANY_PATH.parent.mkdir(parents=True, exist_ok=True)
    PERSONA_PATH.write_text(persona.strip() + "\n", encoding="utf-8")
    COMPANY_PATH.write_text(company.strip() + "\n", encoding="utf-8")
