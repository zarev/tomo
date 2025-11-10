#!/usr/bin/env python3
"""Utility for splitting Rob-o voice lines from a combined MP3 file.

The script mirrors the workflow described in chat:

1. Load a text file containing the expected Rob-o lines (one per line).
2. Transcribe the combined MP3 with Whisper and cache the transcript JSON.
3. Fuzzily align each expected line to the best matching transcript segment.
4. Export individual MP3 clips with optional padding before/after each line.

Place this script next to ``lines.txt`` and the MP3 file, then run it with
``python split_robo_lines.py``.  The output clips are saved in
``rob_o_clips/``.
"""
from __future__ import annotations

import json
from difflib import SequenceMatcher
from pathlib import Path

import whisper
from pydub import AudioSegment


AUDIO_FILE = Path("ElevenLabs_2025-11-10T01_22_51_Rob-o_gen_sp100_s35_sb40_se22_b_m2.mp3")
LINES_FILE = Path("lines.txt")
TRANSCRIPT_JSON = Path("transcript.json")
CLIPS_DIR = Path("rob_o_clips")
WHISPER_MODEL = "base"
PADDING_MS = 300


def load_lines(lines_path: Path) -> list[str]:
    lines = [line.strip() for line in lines_path.read_text(encoding="utf-8").splitlines()]
    return [line for line in lines if line]


def transcribe_audio(audio_path: Path, transcript_json: Path) -> dict:
    print(f"[whisper] Loading model '{WHISPER_MODEL}'...")
    model = whisper.load_model(WHISPER_MODEL)

    print(f"[whisper] Transcribing {audio_path} ...")
    result = model.transcribe(str(audio_path))

    transcript_json.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"[whisper] Saved transcript JSON to {transcript_json}")

    return result


def find_best_match(target: str, segments: list[dict]) -> dict:
    return max(
        segments,
        key=lambda seg: SequenceMatcher(None, target.lower(), seg["text"].lower()).ratio(),
    )


def export_clips(audio_path: Path, segments: list[dict], lines: list[str]) -> None:
    audio = AudioSegment.from_file(audio_path)

    CLIPS_DIR.mkdir(exist_ok=True)
    print(f"[split] Writing clips into {CLIPS_DIR}/")

    for index, line in enumerate(lines, start=1):
        seg = find_best_match(line, segments)

        start_ms = max(int(seg["start"] * 1000) - PADDING_MS, 0)
        end_ms = min(int(seg["end"] * 1000) + PADDING_MS, len(audio))

        clip = audio[start_ms:end_ms]
        clip_name = CLIPS_DIR / f"rob_o_{index:03}.mp3"
        clip.export(clip_name, format="mp3")

        print(
            f"[split] #{index:03}: {clip_name.name} | "
            f"{seg['start']:.2f}s – {seg['end']:.2f}s | "
            f"match='{seg['text'].strip()}'"
        )


def main() -> None:
    if not AUDIO_FILE.exists():
        raise FileNotFoundError(f"Audio file not found: {AUDIO_FILE}")
    if not LINES_FILE.exists():
        raise FileNotFoundError(f"Lines file not found: {LINES_FILE}")

    print("[setup] Loading expected lines…")
    lines = load_lines(LINES_FILE)
    if not lines:
        raise ValueError("No lines found in lines.txt")

    print(f"[setup] Loaded {len(lines)} lines.")

    transcript = transcribe_audio(AUDIO_FILE, TRANSCRIPT_JSON)

    segments = transcript.get("segments")
    if not segments:
        raise ValueError("No segments returned by Whisper transcription")

    export_clips(AUDIO_FILE, segments, lines)

    print("[done] All clips exported!")


if __name__ == "__main__":
    main()
