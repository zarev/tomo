import csv
import os
from typing import Iterable, Dict

import requests

# Input and output files
OPEN_ACCESS_PAPERS_FILE = os.path.join("data", "open_access_papers.csv")
DOWNLOAD_DIR = "papers"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def iter_open_access_papers() -> Iterable[Dict[str, str]]:
    """Yield paper metadata rows from the open access CSV file."""
    try:
        with open(OPEN_ACCESS_PAPERS_FILE, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                title = (row.get("Title") or "").strip()
                url = (row.get("PDF_URL") or "").strip()
                if not url:
                    continue
                yield {"Title": title or "Unknown Title", "PDF_URL": url}
    except FileNotFoundError:
        raise SystemExit(
            f"❌ Could not find '{OPEN_ACCESS_PAPERS_FILE}'. Ensure the open access CSV exists."
        )


def download_pdf(title, url):
    """Download a PDF from URL."""
    safe_title = "".join(c if c.isalnum() or c in " -_()" else "_" for c in title)
    filepath = os.path.join(DOWNLOAD_DIR, f"{safe_title}.pdf")
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        with open(filepath, "wb") as f:
            for chunk in response.iter_content(8192):
                f.write(chunk)
        print(f"✅ {title}")
    except Exception as e:
        print(f"❌ Failed {title}: {e}")

def main():
    papers = list(iter_open_access_papers())

    if not papers:
        print("⚠️ No papers found in the open access CSV.")
        return

    for paper in papers:
        download_pdf(paper["Title"], paper["PDF_URL"])

if __name__ == "__main__":
    main()
