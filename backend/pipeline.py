import csv
import os
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .gemini_cli import GeminiCLIError, is_pipeline_required, run_filter, run_ranker
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

TOP_N_PER_COMPANY = 3
RANK_BATCH_SIZE = int(os.environ.get("RANK_BATCH_SIZE", "25"))
GEMINI_MAX_PEOPLE = int(os.environ.get("GEMINI_MAX_PEOPLE", "80"))
GEMINI_MAX_CANDIDATES_PER_COMPANY = int(os.environ.get("GEMINI_MAX_CANDIDATES_PER_COMPANY", "12"))


@dataclass
class StepResult:
    step_id: str
    title: str
    prompt: str
    before_count: int
    after_count: int
    kept: List[Dict[str, Any]]
    removed: List[Dict[str, Any]]
    kept_justification: str
    removed_justification: str


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
    pipeline_required: bool,
) -> StepResult:
    before_count = len(people)
    kept: List[Dict[str, Any]]
    removed: List[Dict[str, Any]]

    if GEMINI_MAX_PEOPLE and len(people) > GEMINI_MAX_PEOPLE:
        if pipeline_required:
            raise GeminiCLIError("Gemini pipeline required but input exceeds GEMINI_MAX_PEOPLE")
        keep_indices = None
    else:
        try:
            keep_indices = run_filter(prompt, people, context)
        except GeminiCLIError:
            if pipeline_required:
                raise
            keep_indices = None

    if keep_indices is not None:
        kept = [people[i] for i in keep_indices if 0 <= i < len(people)]
        removed = [person for idx, person in enumerate(people) if idx not in keep_indices]
    else:
        if pipeline_required:
            raise GeminiCLIError("Gemini pipeline required but returned no keep_indices")
        kept, removed = _filter_by_keywords(people, fallback_keywords)
        if not kept and people:
            kept, removed = _fallback_reduction(people, fallback_ratio)

    keyword_hint = ", ".join(fallback_keywords[:6]) if fallback_keywords else "role fit and context signals"
    kept_justification = (
        f"Kept candidates that matched {title.lower()} signals (e.g., {keyword_hint})."
    )
    removed_justification = (
        f"Removed candidates that did not match {title.lower()} signals (e.g., {keyword_hint})."
    )

    return StepResult(
        step_id=step_id,
        title=title,
        prompt=prompt,
        before_count=before_count,
        after_count=len(kept),
        kept=kept,
        removed=removed,
        kept_justification=kept_justification,
        removed_justification=removed_justification,
    )


def _infer_stage(company: str, persona: str) -> Tuple[str, List[str]]:
    text = f"{company}\n{persona}".lower()
    if any(token in text for token in ("pre-seed", "preseed", "pre seed")):
        return "pre-seed", STAGE_KEYWORDS["pre-seed"]
    if any(token in text for token in ("series a", "series-a", "seriesa", "growth stage", "scaleup", "scale-up")):
        return "seed", STAGE_KEYWORDS["seed"]
    if "seed" in text:
        return "seed", STAGE_KEYWORDS["seed"]
    return "pre-seed", STAGE_KEYWORDS["pre-seed"]


def _match_keywords(person: Dict[str, Any], keywords: List[str]) -> List[str]:
    if not keywords:
        return []
    haystack = " ".join(
        str(person.get(key, ""))
        for key in ("name", "title", "company", "notes", "location", "industry")
    ).lower()
    hits = []
    for keyword in keywords:
        if keyword in haystack:
            hits.append(keyword)
    return hits


def _heuristic_ranking(
    people: List[Dict[str, Any]],
    persona_keywords: List[str],
    company_keywords: List[str],
    stage_keywords: List[str],
    top_n: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    if not people:
        return [], []

    scored: List[Dict[str, Any]] = []
    for idx, person in enumerate(people):
        persona_hits = _match_keywords(person, persona_keywords)
        company_hits = _match_keywords(person, company_keywords)
        stage_hits = _match_keywords(person, stage_keywords)
        seniority_bonus = 1 if re.search(r"\b(head|lead|vp|chief|director|founder|c[eo]o)\b", str(person.get("title", "")).lower()) else 0
        score = (len(persona_hits) * 3) + (len(company_hits) * 2) + len(stage_hits) + seniority_bonus
        scored.append(
            {
                "index": idx,
                "person": dict(person),
                "score": float(score),
                "persona_hits": persona_hits,
                "company_hits": company_hits,
                "stage_hits": stage_hits,
            }
        )

    if not scored:
        return [], []

    max_score = max(item["score"] for item in scored) or 1.0
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for item in scored:
        company = item["person"].get("company") or "Unknown Company"
        grouped[company].append(item)

    ranked: List[Dict[str, Any]] = []
    demoted: List[Dict[str, Any]] = []

    for company_items in grouped.values():
        company_items.sort(key=lambda entry: (entry["score"], len(entry["persona_hits"]), len(entry["company_hits"])), reverse=True)
        for rank, entry in enumerate(company_items, start=1):
            person_copy = dict(entry["person"])
            person_copy["score"] = round(entry["score"], 3)
            person_copy["score_normalized"] = round(entry["score"] / max_score, 3)
            person_copy["company_rank"] = rank
            reasons = []
            if entry["persona_hits"]:
                reasons.append(f"Persona keywords: {', '.join(entry['persona_hits'][:4])}")
            if entry["company_hits"]:
                reasons.append(f"Company focus: {', '.join(entry['company_hits'][:4])}")
            if entry["stage_hits"]:
                reasons.append(f"Stage signals: {', '.join(entry['stage_hits'][:4])}")
            if rank == 1 and not reasons:
                reasons.append("Best fit based on available data")
            person_copy["reason"] = "; ".join(reasons)
            if rank <= top_n:
                ranked.append(person_copy)
            else:
                demoted.append(person_copy)

    ranked.sort(key=lambda person: (person.get("company", ""), person.get("company_rank", 0)))
    return ranked, demoted


def _score_company_people(
    entries: List[Tuple[int, Dict[str, Any]]],
    persona_keywords: List[str],
    company_keywords: List[str],
    stage_keywords: List[str],
) -> List[Tuple[int, Dict[str, Any], float]]:
    scored: List[Tuple[int, Dict[str, Any], float]] = []
    for idx, person in entries:
        persona_hits = _match_keywords(person, persona_keywords)
        company_hits = _match_keywords(person, company_keywords)
        stage_hits = _match_keywords(person, stage_keywords)
        seniority_bonus = 1 if re.search(r"\b(head|lead|vp|chief|director|founder|c[eo]o)\b", str(person.get("title", "")).lower()) else 0
        score = (len(persona_hits) * 3) + (len(company_hits) * 2) + len(stage_hits) + seniority_bonus
        scored.append((idx, person, float(score)))
    scored.sort(key=lambda item: item[2], reverse=True)
    return scored


def _rank_people(
    people: List[Dict[str, Any]],
    stage_label: str,
    persona: str,
    company: str,
    persona_keywords: List[str],
    company_keywords: List[str],
    stage_keywords: List[str],
    top_n: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    pipeline_required = is_pipeline_required()
    grouped_people: Dict[str, List[Tuple[int, Dict[str, Any]]]] = defaultdict(list)
    for idx, person in enumerate(people):
        company_key = person.get("company") or "Unknown Company"
        grouped_people[company_key].append((idx, person))

    annotated: List[Dict[str, Any]] = []
    ranked: List[Dict[str, Any]] = []
    demoted: List[Dict[str, Any]] = []

    for company_key, entries in grouped_people.items():
        company_rankings: List[Dict[str, Any]] = []
        demoted_candidates: List[Dict[str, Any]] = []

        scored_entries = _score_company_people(entries, persona_keywords, company_keywords, stage_keywords)
        if GEMINI_MAX_CANDIDATES_PER_COMPANY > 0:
            scored_entries = scored_entries[:GEMINI_MAX_CANDIDATES_PER_COMPANY]

        candidate_entries = [(idx, person) for idx, person, _ in scored_entries]
        non_candidate_indices = {idx for idx, _, _ in scored_entries}
        for idx, person in entries:
            if idx not in non_candidate_indices:
                person_copy = dict(person)
                person_copy.setdefault("reason", "Filtered out before AI ranking")
                demoted_candidates.append(person_copy)

        chunks: List[List[Tuple[int, Dict[str, Any]]]] = []
        if RANK_BATCH_SIZE > 0 and len(candidate_entries) > RANK_BATCH_SIZE:
            for i in range(0, len(candidate_entries), RANK_BATCH_SIZE):
                chunks.append(candidate_entries[i:i + RANK_BATCH_SIZE])
        else:
            chunks.append(candidate_entries)

        for chunk in chunks:
            chunk_people = [person for _, person in chunk]
            index_map = [idx for idx, _ in chunk]
            try:
                rankings = run_ranker(
                    chunk_people,
                    persona=persona,
                    company=company,
                    stage=stage_label,
                    top_n_per_company=top_n,
                )
            except GeminiCLIError:
                if pipeline_required:
                    raise
                rankings = None

            if not rankings:
                if pipeline_required:
                    raise GeminiCLIError("Gemini pipeline required but returned no rankings")
                ranked_chunk, _ = _heuristic_ranking(chunk_people, persona_keywords, company_keywords, stage_keywords, top_n)
                for person in ranked_chunk:
                    person_copy = dict(person)
                    person_copy.setdefault("reason", "Heuristic ranking (Gemini unavailable)")
                    company_rankings.append({"person": person_copy, "score": person_copy.get("score", 0.0)})
                continue

            for entry in rankings:
                idx = entry.get("index")
                if idx is None:
                    continue
                try:
                    idx = int(idx)
                except (TypeError, ValueError):
                    continue
                if idx < 0 or idx >= len(index_map):
                    continue
                person_copy = dict(chunk_people[idx])
                score = entry.get("score")
                if isinstance(score, str):
                    try:
                        score = float(score)
                    except ValueError:
                        score = 0.0
                person_copy["score"] = round(float(score or 0.0), 3)
                norm = entry.get("score_normalized")
                if norm is not None:
                    try:
                        person_copy["score_normalized"] = round(float(norm), 3)
                    except ValueError:
                        pass
                reason = entry.get("reason")
                if isinstance(reason, str):
                    person_copy["reason"] = reason.strip()
                company_rankings.append({"person": person_copy, "score": person_copy["score"]})

        if not company_rankings:
            if pipeline_required:
                raise GeminiCLIError("Gemini pipeline required but produced no company rankings")
            fallback_ranked, fallback_demoted = _heuristic_ranking(
                [person for _, person in entries],
                persona_keywords,
                company_keywords,
                stage_keywords,
                top_n,
            )
            ranked.extend(fallback_ranked)
            demoted.extend(fallback_demoted + demoted_candidates)
            continue

        company_rankings.sort(key=lambda item: item.get("score", 0.0), reverse=True)
        for rank, entry in enumerate(company_rankings, start=1):
            person_copy = dict(entry["person"])
            person_copy["company_rank"] = rank
            annotated.append(person_copy)
            if rank <= top_n:
                ranked.append(person_copy)
            else:
                demoted.append(person_copy)

        if demoted_candidates:
            demoted.extend(demoted_candidates)

    if ranked:
        ranked.sort(key=lambda person: (person.get("company", ""), person.get("company_rank", 0)))
        return ranked, demoted

    return _heuristic_ranking(people, persona_keywords, company_keywords, stage_keywords, top_n)


def run_pipeline(
    people: List[Dict[str, Any]],
    prompts: List[PromptStep],
    persona: str,
    company: str,
) -> Tuple[List[StepResult], List[Dict[str, Any]], str]:
    stage_label, stage_keywords = _infer_stage(company, persona)
    persona_keywords = _extract_keywords(persona)
    company_keywords = _extract_keywords(company)
    pipeline_required = is_pipeline_required()

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
            "stage": stage_label,
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
            pipeline_required,
        )
        results.append(result)
        current_people = result.kept

    ranked, demoted = _rank_people(
        current_people,
        stage_label=stage_label,
        persona=persona,
        company=company,
        persona_keywords=persona_keywords,
        company_keywords=company_keywords,
        stage_keywords=stage_keywords,
        top_n=TOP_N_PER_COMPANY,
    )

    if results:
        final_step = results[-1]
        final_step.after_count = len(ranked)
        final_step.kept = ranked
        final_step.removed = final_step.removed + demoted
        final_step.kept_justification = (
            "Kept top-ranked contacts per company based on persona match and role seniority."
        )
        final_step.removed_justification = (
            "Removed lower-ranked contacts per company after scoring and ranking."
        )

    return results, ranked, stage_label


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
