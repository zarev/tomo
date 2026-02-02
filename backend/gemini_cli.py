import json
import os
import re
import shlex
import subprocess
from typing import Any, Dict, List, Optional


class GeminiCLIError(RuntimeError):
    pass


def is_enabled() -> bool:
    return os.environ.get("GEMINI_CLI_ENABLED", "").lower() in {"1", "true", "yes"}


def is_pipeline_enabled() -> bool:
    return os.environ.get("GEMINI_PIPELINE_ENABLED", "").lower() in {"1", "true", "yes"}


def is_pipeline_required() -> bool:
    return os.environ.get("GEMINI_PIPELINE_REQUIRED", "").lower() in {"1", "true", "yes"}


def _run_prompt(payload: Dict[str, Any], api_key: Optional[str] = None) -> Dict[str, Any]:
    command = os.environ.get(
        "GEMINI_CLI_COMMAND",
        "gemini --output-format json --prompt",
    )
    timeout_seconds = float(os.environ.get("GEMINI_CLI_TIMEOUT", "45"))
    cmd_parts = shlex.split(command)
    prompt_text = payload.get("prompt", "")
    context_blob = json.dumps({k: v for k, v in payload.items() if k != "prompt"})
    full_prompt = f"{prompt_text}\n\nContext:\n{context_blob}"
    cmd_parts.append(full_prompt)
    env = os.environ.copy()
    if api_key:
        env["GEMINI_API_KEY"] = api_key
        env["GOOGLE_API_KEY"] = api_key

    try:
        result = subprocess.run(
            cmd_parts,
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            check=True,
            env=env,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise GeminiCLIError(f"Gemini CLI timed out after {timeout_seconds}s") from exc
    except (OSError, subprocess.CalledProcessError) as exc:
        stderr = getattr(exc, "stderr", "") or ""
        stdout = getattr(exc, "stdout", "") or ""
        raise GeminiCLIError(
            f"{exc}; stdout={stdout.strip()} stderr={stderr.strip()}"
        ) from exc

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise GeminiCLIError("Gemini CLI did not return valid JSON") from exc


def _strip_code_fences(text: str) -> str:
    """Remove simple Markdown code fences around content."""
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()
    try:
        end_idx = next(idx for idx, line in enumerate(lines[1:], start=1) if line.startswith("```"))
        return "\n".join(lines[1:end_idx]).strip()
    except StopIteration:
        return stripped


def _extract_company_profile_from_text(text: str) -> Optional[str]:
    """Heuristic extraction when JSON parsing fails.

    Looks for a "company_profile_md" field inside an otherwise non-JSON string.
    Uses a greedy pattern that stops at an unescaped quote followed by whitespace
    and either a closing brace or another key.
    """

    # Match the key and capture everything until we hit an unescaped " followed by } or ,"
    match = re.search(
        r'"company_profile_md"\s*:\s*"((?:[^"\\]|\\.)*)"\s*[,}]',
        text,
        flags=re.DOTALL,
    )
    if not match:
        # Fallback: try to grab from the key to the end of the string
        match = re.search(r'"company_profile_md"\s*:\s*"((?:[^"\\]|\\.)*)"', text, flags=re.DOTALL)
        if not match:
            return None

    value = match.group(1)
    # Unescape common JSON escape sequences.
    value = value.replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"').replace("\\\\", "\\")
    return value.strip()


def _unwrap_company_profile(data: Any) -> Optional[str]:
    """Extract markdown content from varied Gemini responses.

    The CLI may return nested dicts, lists, or even a JSON string. This walks the
    structure to pull out the first useful markdown blob.
    """

    if data is None:
        return None

    if isinstance(data, str):
        text = data.strip()
        if not text:
            return None

        # Peel off code fences first, then attempt JSON parsing again.
        text = _strip_code_fences(text)
        if text.startswith("{") or text.startswith("["):
            try:
                parsed = json.loads(text)
                return _unwrap_company_profile(parsed)
            except json.JSONDecodeError:
                extracted = _extract_company_profile_from_text(text)
                if extracted:
                    return extracted
            return None

        extracted = _extract_company_profile_from_text(text)
        if extracted:
            return extracted

        return text

    if isinstance(data, dict):
        for key in ("company_profile_md", "company_profile", "profile", "text", "response", "content"):
            if key in data:
                extracted = _unwrap_company_profile(data[key])
                if extracted:
                    return extracted
        for value in data.values():
            extracted = _unwrap_company_profile(value)
            if extracted:
                return extracted
        return None

    if isinstance(data, list):
        for item in data:
            extracted = _unwrap_company_profile(item)
            if extracted:
                return extracted
        return None

    return None


def run_filter(prompt: str, people: List[Dict[str, Any]], context: Dict[str, Any]) -> Optional[List[int]]:
    if not is_enabled() or not is_pipeline_enabled():
        return None

    payload = {
        "prompt": prompt,
        "people": people,
        "context": context,
        "instruction": (
            "Return JSON with a key 'keep_indices' containing the indices of people to keep."
        ),
    }
    response = _run_prompt(payload)

    keep_indices = response.get("keep_indices")
    if not isinstance(keep_indices, list):
        raise GeminiCLIError("Gemini CLI response missing keep_indices")

    return [int(idx) for idx in keep_indices]


def run_company_research(prompt: str, context: Dict[str, Any], api_key: Optional[str] = None) -> Optional[str]:
    if not is_enabled():
        return None

    payload = {
        "prompt": prompt,
        "context": context,
        "instruction": (
            "Return JSON with key 'company_profile_md' containing a concise markdown summary of recent publications, funding news, and product updates about Throxy."
        ),
    }

    response = _run_prompt(payload, api_key=api_key)

    if isinstance(response, dict):
        candidate = response.get("company_profile_md")
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()

    extracted = _unwrap_company_profile(response)
    if extracted and not extracted.strip().startswith("{"):
        return extracted.strip()

    return None


def run_ranker(
    people: List[Dict[str, Any]],
    persona: str,
    company: str,
    stage: str,
    top_n_per_company: int = 3,
    api_key: Optional[str] = None,
) -> Optional[List[Dict[str, Any]]]:
    if not is_enabled() or not is_pipeline_enabled():
        return None

    payload = {
        "prompt": (
            "You are an expert outbound strategist. Rank leads against the target persona."
            " Return only the most relevant contacts per company."
        ),
        "instruction": (
            "Return JSON with key 'rankings' as a list of objects with: index (int), score (0-1 float),"
            " company_rank (1 = best for that company), and reason (string)."
            " Include only up to top_n_per_company leads per company."
        ),
        "people": people,
        "persona": persona,
        "company_profile": company,
        "stage": stage,
        "top_n_per_company": top_n_per_company,
    }

    response = _run_prompt(payload, api_key=api_key)

    rankings = response.get("rankings")
    if rankings is None and isinstance(response, dict):
        for key in ("results", "ranked", "ranking"):
            if key in response:
                rankings = response[key]
                break

    if not isinstance(rankings, list):
        raise GeminiCLIError("Gemini CLI response missing rankings")

    cleaned: List[Dict[str, Any]] = []
    for entry in rankings:
        if isinstance(entry, dict):
            cleaned.append(entry)
        elif isinstance(entry, (list, tuple)) and entry:
            try:
                idx = int(entry[0])
            except (TypeError, ValueError):
                continue
            cleaned.append({"index": idx, "score": entry[1] if len(entry) > 1 else None})

    return cleaned


def run_simple_prompt(prompt: str, api_key: Optional[str] = None) -> str:
    if not is_enabled():
        raise GeminiCLIError("Gemini CLI not enabled")

    payload = {
        "prompt": prompt,
        "context": {},
        "instruction": "Return JSON with a key 'text' containing the assistant reply.",
    }

    response = _run_prompt(payload, api_key=api_key)

    for key in ("text", "response", "content", "company_profile_md"):
        val = response.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()

    for val in response.values():
        if isinstance(val, str) and val.strip():
            return val.strip()

    raise GeminiCLIError("Gemini CLI returned no text")
