from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence


@dataclass(frozen=True)
class Paper:
    """Representation of an open access paper entry."""

    title: str
    pdf_url: str


@dataclass(frozen=True)
class Source:
    """Representation of a source website entry."""

    url: str


@dataclass(frozen=True)
class ScrapeJob:
    """Pairing of a source with a paper to be scraped."""

    source: Source
    paper: Paper


class InputFileError(ValueError):
    """Raised when an input CSV file is missing required information."""


REQUIRED_PAPER_HEADERS = {"Title", "PDF_URL"}
REQUIRED_SOURCE_HEADERS = {"Website"}


def _normalise_path(path: Path | str) -> Path:
    resolved = Path(path)
    if not resolved.exists():
        raise FileNotFoundError(f"Input file not found: {resolved}")
    return resolved


def load_open_access_papers(path: Path | str) -> List[Paper]:
    """Load paper entries from ``open_access_papers.csv``."""

    file_path = _normalise_path(path)
    with file_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        headers = set(reader.fieldnames or [])
        missing_headers = REQUIRED_PAPER_HEADERS - headers
        if missing_headers:
            raise InputFileError(
                f"Missing required paper columns {sorted(missing_headers)} in {file_path}"
            )

        papers: List[Paper] = []
        for index, row in enumerate(reader, start=2):
            title = (row.get("Title") or "").strip()
            pdf_url = (row.get("PDF_URL") or "").strip()
            if not title or not pdf_url:
                raise InputFileError(
                    f"Row {index} in {file_path} is missing title or PDF URL."
                )
            papers.append(Paper(title=title, pdf_url=pdf_url))

    if not papers:
        raise InputFileError(f"No paper entries were found in {file_path}.")

    return papers


def load_sources(path: Path | str) -> List[Source]:
    """Load source entries from ``sources.csv``."""

    file_path = _normalise_path(path)
    with file_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        headers = set(reader.fieldnames or [])
        missing_headers = REQUIRED_SOURCE_HEADERS - headers
        if missing_headers:
            raise InputFileError(
                f"Missing required source columns {sorted(missing_headers)} in {file_path}"
            )

        sources: List[Source] = []
        for index, row in enumerate(reader, start=2):
            url = (row.get("Website") or "").strip()
            if not url:
                raise InputFileError(
                    f"Row {index} in {file_path} is missing a website URL."
                )
            sources.append(Source(url=url))

    if not sources:
        raise InputFileError(f"No source entries were found in {file_path}.")

    return sources


def build_scrape_jobs(
    sources: Sequence[Source], papers: Sequence[Paper]
) -> List[ScrapeJob]:
    """Combine sources and papers into scrape jobs."""

    if not sources:
        raise InputFileError("At least one source is required to build scrape jobs.")
    if not papers:
        raise InputFileError("At least one paper is required to build scrape jobs.")

    return [ScrapeJob(source=source, paper=paper) for source in sources for paper in papers]


def iter_paper_urls(papers: Iterable[Paper]) -> Iterable[str]:
    """Yield PDF URLs from the provided paper entries."""

    for paper in papers:
        yield paper.pdf_url
