import json
import os
import shlex
import subprocess
from typing import Any, Dict, List, Optional


class GeminiCLIError(RuntimeError):
    pass


def is_enabled() -> bool:
    return os.environ.get("GEMINI_CLI_ENABLED", "").lower() in {"1", "true", "yes"}


def run_filter(prompt: str, people: List[Dict[str, Any]], context: Dict[str, Any]) -> Optional[List[int]]:
    if not is_enabled():
        return None

    command = os.environ.get(
        "GEMINI_CLI_COMMAND",
        "gemini --mcp chrome-dev-tools --json",
    )
    cmd_parts = shlex.split(command)
    payload = {
        "prompt": prompt,
        "people": people,
        "context": context,
        "instruction": (
            "Return JSON with a key 'keep_indices' containing the indices of people to keep."
        ),
    }

    try:
        result = subprocess.run(
            cmd_parts,
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise GeminiCLIError(str(exc)) from exc

    try:
        response = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise GeminiCLIError("Gemini CLI did not return valid JSON") from exc

    keep_indices = response.get("keep_indices")
    if not isinstance(keep_indices, list):
        raise GeminiCLIError("Gemini CLI response missing keep_indices")

    return [int(idx) for idx in keep_indices]
