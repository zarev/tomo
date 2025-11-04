"""Convert a PDF into Markdown using Gemini 1.5 Pro and extracted images.

This script splits the pages of a PDF into JPEG images and sends each page to
Google's Gemini API requesting a Markdown reconstruction of the content. The
Markdown for each page is saved to a single output file, with page images stored
in a dedicated directory.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import List

from google.api_core.exceptions import DeadlineExceeded, ResourceExhausted
import google.generativeai as genai
from pdf2image import convert_from_path
from PIL import Image
from tqdm import tqdm


PDF_PATH = "input.pdf"
OUTPUT_MD = "output_with_images.md"
IMAGES_DIR = "pdf_images"
API_KEY = os.getenv("GEMINI_API_KEY") or "YOUR_GEMINI_API_KEY"
MODEL_NAME = "gemini-1.5-pro"
DPI = 200
RETRY_LIMIT = 3
IMAGE_QUALITY = 80


def split_pdf_to_images(
    pdf_path: str,
    dpi: int,
    converter=convert_from_path,
) -> List[Image.Image]:
    """Split a PDF into images using the provided DPI."""

    return converter(pdf_path, dpi=dpi)


def extract_markdown_from_pages(
    pages: List[Image.Image],
    images_dir: str = IMAGES_DIR,
    image_quality: int = IMAGE_QUALITY,
    retry_limit: int = RETRY_LIMIT,
    api_key: str = API_KEY,
    model_name: str = MODEL_NAME,
    sleep_fn=time.sleep,
    genai_module=genai,
    model=None,
) -> List[str]:
    """Process each page image through Gemini and return Markdown snippets."""

    if model is None:
        genai_module.configure(api_key=api_key)
        model = genai_module.GenerativeModel(model_name)

    Path(images_dir).mkdir(exist_ok=True)

    results: List[str] = []
    for i, page in enumerate(tqdm(pages, desc="Processing pages")):
        img_name = f"page_{i + 1}.jpg"
        img_path = os.path.join(images_dir, img_name)

        page.save(img_path, "JPEG", quality=image_quality)

        for attempt in range(retry_limit):
            try:
                with open(img_path, "rb") as image_file:
                    prompt = (
                        "Extract this page into Markdown, keeping tables, code, and layout. "
                        "If this page includes images, refer to them as "
                        f"`![Page {i + 1}]({img_path})` at the appropriate place in the text."
                    )
                    response = model.generate_content([image_file, prompt])
                results.append(f"## Page {i + 1}\n\n{response.text}")
                break
            except (ResourceExhausted, DeadlineExceeded):
                print(f"Retry {attempt + 1} for page {i + 1} due to rate/time limits.")
                sleep_fn(5)
            except Exception as exc:  # pragma: no cover - defensive programming
                print(f"Error on page {i + 1}: {exc}")
                results.append(f"\n<!-- Page {i + 1} failed -->\n")
                break
    return results


def save_markdown(snippets: List[str], output_path: str = OUTPUT_MD) -> None:
    """Save the combined Markdown output to disk."""
    markdown_output = "\n\n---\n\n".join(snippets)
    with open(output_path, "w", encoding="utf-8") as output_file:
        output_file.write(markdown_output)



def main() -> None:
    pages = split_pdf_to_images(PDF_PATH, DPI)
    markdown_snippets = extract_markdown_from_pages(pages)
    save_markdown(markdown_snippets)
    print(f"\n✅ Done! Markdown saved to: {OUTPUT_MD}")
    print(f"🖼️ Images stored in: {IMAGES_DIR}/")


if __name__ == "__main__":
    main()
