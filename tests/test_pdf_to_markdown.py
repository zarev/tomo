from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from typing import List

import pytest


def _load_pdf_to_markdown_module():
    module_path = Path(__file__).resolve().parents[1] / "pdf_to_markdown.py"

    google_module = types.ModuleType("google")
    api_core_module = types.ModuleType("google.api_core")
    exceptions_module = types.ModuleType("google.api_core.exceptions")

    class _TransientError(Exception):
        pass

    exceptions_module.ResourceExhausted = _TransientError
    exceptions_module.DeadlineExceeded = _TransientError

    api_core_module.exceptions = exceptions_module
    google_module.api_core = api_core_module

    generative_module = types.ModuleType("google.generativeai")

    class DummyGenerativeModel:
        def __init__(self, *_args, **_kwargs):  # pragma: no cover - stub
            raise AssertionError("This stub should not be instantiated in tests")

    def configure(**_kwargs):  # pragma: no cover - stub
        raise AssertionError("configure should not be called in tests")

    generative_module.GenerativeModel = DummyGenerativeModel
    generative_module.configure = configure

    sys.modules.setdefault("google", google_module)
    sys.modules.setdefault("google.api_core", api_core_module)
    sys.modules.setdefault("google.api_core.exceptions", exceptions_module)
    sys.modules.setdefault("google.generativeai", generative_module)

    pdf2image_module = types.ModuleType("pdf2image")

    def _convert_from_path(*_args, **_kwargs):  # pragma: no cover - stub
        raise AssertionError("pdf2image.convert_from_path should not be used in tests")

    pdf2image_module.convert_from_path = _convert_from_path

    pil_module = types.ModuleType("PIL")
    pil_image_module = types.ModuleType("PIL.Image")

    class _PlaceholderImage:  # pragma: no cover - stub
        pass

    pil_image_module.Image = _PlaceholderImage
    pil_module.Image = pil_image_module

    tqdm_module = types.ModuleType("tqdm")

    def _tqdm(iterable, **_kwargs):  # pragma: no cover - stub
        return iterable

    tqdm_module.tqdm = _tqdm

    sys.modules.setdefault("pdf2image", pdf2image_module)
    sys.modules.setdefault("PIL", pil_module)
    sys.modules.setdefault("PIL.Image", pil_image_module)
    sys.modules.setdefault("tqdm", tqdm_module)

    spec = importlib.util.spec_from_file_location("pdf_to_markdown", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["pdf_to_markdown"] = module
    assert spec.loader is not None  # for mypy
    spec.loader.exec_module(module)
    return module


ptm = _load_pdf_to_markdown_module()


class DummyResponse:
    def __init__(self, text: str) -> None:
        self.text = text


class DummyModel:
    def __init__(self, responses: List[str]) -> None:
        self._responses = iter(responses)
        self.calls = []

    def generate_content(self, args):
        self.calls.append(args)
        return DummyResponse(next(self._responses))


class DummyImage:
    def __init__(self) -> None:
        self.saved_paths = []

    def save(self, path: str, _format: str, quality: int) -> None:  # pragma: no cover - trivial
        self.saved_paths.append((path, quality))
        Path(path).write_bytes(b"fake image data")


@pytest.fixture()
def sample_image() -> DummyImage:
    return DummyImage()


def test_extract_markdown_from_pages_saves_images_and_returns_markdown(tmp_path: Path, sample_image: DummyImage):
    images_dir = tmp_path / "images"
    dummy_model = DummyModel(["markdown output"])

    snippets = ptm.extract_markdown_from_pages(
        [sample_image],
        images_dir=str(images_dir),
        model=dummy_model,
        genai_module=None,  # bypass configuration
    )

    assert snippets == ["## Page 1\n\nmarkdown output"]
    expected_image = images_dir / "page_1.jpg"
    assert expected_image.exists()
    assert dummy_model.calls[0][1] == (
        "Extract this page into Markdown, keeping tables, code, and layout. "
        "If this page includes images, refer to them as "
        f"`![Page 1]({expected_image})` at the appropriate place in the text."
    )


def test_extract_markdown_retries_on_transient_errors(tmp_path: Path, sample_image: DummyImage):
    images_dir = tmp_path / "images"

    class FlakyModel:
        def __init__(self) -> None:
            self.calls = 0

        def generate_content(self, _):
            self.calls += 1
            if self.calls == 1:
                raise ptm.ResourceExhausted("transient")
            return DummyResponse("second attempt")

    sleep_calls = []

    def fake_sleep(seconds: int) -> None:  # pragma: no cover - trivial
        sleep_calls.append(seconds)

    model = FlakyModel()

    snippets = ptm.extract_markdown_from_pages(
        [sample_image],
        images_dir=str(images_dir),
        model=model,
        genai_module=None,
        retry_limit=3,
        sleep_fn=fake_sleep,
    )

    assert snippets == ["## Page 1\n\nsecond attempt"]
    assert sleep_calls == [5]
    assert model.calls == 2


def test_save_markdown_writes_joined_output(tmp_path: Path):
    output_path = tmp_path / "output.md"

    ptm.save_markdown(["first", "second"], output_path=str(output_path))

    assert output_path.read_text(encoding="utf-8") == "first\n\n---\n\nsecond"


def test_split_pdf_to_images_uses_provided_converter():
    calls = {}

    def fake_convert(path, dpi):
        calls["path"] = path
        calls["dpi"] = dpi
        return ["image"]

    result = ptm.split_pdf_to_images("some.pdf", 144, converter=fake_convert)

    assert result == ["image"]
    assert calls == {"path": "some.pdf", "dpi": 144}
