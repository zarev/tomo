from pathlib import Path
import sys

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import web_scraper

DATA_DIR = ROOT_DIR / "data"


def test_load_open_access_papers_returns_expected_entries():
    papers = web_scraper.load_open_access_papers(DATA_DIR / "open_access_papers.csv")

    assert len(papers) == 2
    assert papers[0].title == (
        "Dissimilar laser welding of an as-rolled CoCrFeMnNi high entropy alloy to Inconel 718 superalloy"
    )
    assert papers[0].pdf_url.startswith("https://www.sciencedirect.com/")
    assert papers[1].title.startswith("Multiscale characterization of NiTi shape memory alloy")


def test_load_sources_returns_expected_entries():
    sources = web_scraper.load_sources(DATA_DIR / "sources.csv")

    assert sources == [
        web_scraper.Source(
            "https://photon-science.desy.de/facilities/petra_iii/beamlines/p07_high_energy_materials_science/publications_from_p07/2025/index_eng.html"
        )
    ]


def test_build_scrape_jobs_pairs_each_source_with_each_paper():
    papers = web_scraper.load_open_access_papers(DATA_DIR / "open_access_papers.csv")
    sources = web_scraper.load_sources(DATA_DIR / "sources.csv")

    jobs = web_scraper.build_scrape_jobs(sources, papers)

    assert len(jobs) == len(sources) * len(papers)
    assert jobs[0].source == sources[0]
    assert jobs[0].paper == papers[0]
    assert jobs[1].paper == papers[1]


def test_build_scrape_jobs_requires_sources_or_papers():
    papers = web_scraper.load_open_access_papers(DATA_DIR / "open_access_papers.csv")
    sources = web_scraper.load_sources(DATA_DIR / "sources.csv")

    with pytest.raises(web_scraper.InputFileError):
        web_scraper.build_scrape_jobs([], papers)

    with pytest.raises(web_scraper.InputFileError):
        web_scraper.build_scrape_jobs(sources, [])
