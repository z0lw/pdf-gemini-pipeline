#!/usr/bin/env python3
"""Split PDFs, run Yomitoku HTML on each half page, then ask Gemini for JSON."""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import subprocess
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence

import fitz  # PyMuPDF
import google.generativeai as genai
from pypdf import PdfReader, PdfWriter

ROOT = Path(__file__).resolve().parent
DOTENV = ROOT / ".env"


@dataclass
class Config:
    pdf: Optional[Path]
    pdf_dir: Optional[Path]
    prompt_path: Path
    output_dir: Path
    device: str
    model: str
    yomitoku_cmd: Path
    max_workers: int = 4
    max_page_workers: int = 4


@dataclass
class HalfPage:
    page_index: int
    side: str  # l / r
    pdf_path: Path
    image_path: Path

    @property
    def label(self) -> str:
        return f"p{self.page_index + 1:02d}_{self.side}"


def load_env(path: Path = DOTENV) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


def _env_path(key: str, fallback: Optional[Path]) -> Optional[Path]:
    value = os.environ.get(key)
    if value is None:
        return fallback
    if not value:
        return None
    return Path(value).expanduser()


def _env_text(key: str, default: str) -> str:
    value = os.environ.get(key)
    return value if value else default


def resolve_config() -> Config:
    load_env()
    pdf = _env_path("PDF_INPUT", None)
    pdf_dir = _env_path("PDF_INPUT_DIR", ROOT / "input_pdfs")
    prompt_path = (_env_path("PROMPT_PATH", ROOT / "prompt.md") or (ROOT / "prompt.md")).resolve()
    output_dir = (_env_path("OUTPUT_DIR", ROOT / "outputs") or (ROOT / "outputs")).resolve()
    device = _env_text("DEVICE", "cuda")
    model = _env_text("GEMINI_MODEL", "models/gemini-2.5-flash")
    yomitoku_cmd = (_env_path("YOMITOKU_CMD", ROOT / "yomitoku") or (ROOT / "yomitoku")).resolve()
    max_workers = int(_env_text("MAX_WORKERS", "4"))
    max_page_workers = int(_env_text("MAX_PAGE_WORKERS", "4"))
    pdf_dir = pdf_dir.resolve() if pdf_dir else None
    pdf = pdf.resolve() if pdf else None
    return Config(pdf, pdf_dir, prompt_path, output_dir, device, model, yomitoku_cmd, max_workers, max_page_workers)


def iter_pdfs(single: Optional[Path], folder: Optional[Path]) -> List[Path]:
    if single:
        if not single.exists():
            raise FileNotFoundError(single)
        return [single]
    if folder is None:
        raise ValueError("PDF_INPUT or PDF_INPUT_DIR must be set.")
    if not folder.exists():
        raise FileNotFoundError(folder)
    pdfs = sorted(folder.glob("*.pdf"))
    if not pdfs:
        raise FileNotFoundError(f"No PDFs in {folder}")
    return pdfs


def safe_name(path: Path) -> str:
    text = path.stem
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in text)
    cleaned = cleaned.strip("_")
    return cleaned or "pdf"


def split_pdf(pdf_path: Path, out_dir: Path) -> List[HalfPage]:
    reader = PdfReader(str(pdf_path))
    halves: List[HalfPage] = []
    (out_dir / "pdf_pages").mkdir(parents=True, exist_ok=True)

    for page_index, page in enumerate(reader.pages):
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        x_mid = width / 2.0

        for side, (x0, x1) in {"l": (0.0, x_mid), "r": (x_mid, width)}.items():
            writer = PdfWriter()
            new_page = copy.deepcopy(page)
            new_page.mediabox.lower_left = (x0, 0.0)
            new_page.mediabox.upper_right = (x1, height)
            writer.add_page(new_page)

            half_pdf = out_dir / "pdf_pages" / f"{pdf_path.stem}_p{page_index + 1:02d}_{side.upper()}.pdf"
            with half_pdf.open("wb") as handle:
                writer.write(handle)

            half_png = half_pdf.with_suffix(".png")
            render_pdf_page(half_pdf, half_png)
            halves.append(HalfPage(page_index, side, half_pdf, half_png))
    return halves


def render_pdf_page(pdf_path: Path, png_path: Path, dpi: int = 300) -> None:
    doc = fitz.open(pdf_path)
    try:
        page = doc[0]
        pix = page.get_pixmap(dpi=dpi)
        pix.save(png_path)
    finally:
        doc.close()


def run_yomitoku(image_path: Path, page_dir: Path, device: str, yomitoku_cmd: Path) -> Path:
    page_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(yomitoku_cmd),
        str(image_path),
        "-f",
        "html",
        "-o",
        str(page_dir),
        "-d",
        device,
    ]
    subprocess.run(cmd, check=True)
    html_files = sorted(page_dir.glob("*.html"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not html_files:
        raise FileNotFoundError(f"No Yomitoku HTML in {page_dir}")
    return html_files[0]


def build_model(api_key: str, model_name: str):
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(model_name)


def upload_file(path: Path):
    return genai.upload_file(path=str(path))


def call_gemini(model, prompt_text: str, pdf_path: Path, html_path: Path) -> str:
    uploads = []
    try:
        pdf_file = upload_file(pdf_path)
        html_file = upload_file(html_path)
        uploads.extend([pdf_file, html_file])
        response = model.generate_content(
            [prompt_text, pdf_file, html_file],
            request_options={"timeout": 600},
        )
        return response.text or ""
    finally:
        for uploaded in uploads:
            try:
                genai.delete_file(uploaded.name)
            except Exception:
                pass


CODE_FENCE = re.compile(r"```(?:json|javascript|js)?\s*([\s\S]+?)\s*```", re.IGNORECASE)


def _extract_json_payload(payload: str) -> tuple[str, Optional[object]]:
    """Return cleaned text plus parsed JSON if possible."""
    text = payload.strip()
    match = CODE_FENCE.search(text)
    if match:
        text = match.group(1).strip()
    text = text.lstrip("\ufeff").lstrip()
    start_index = next((idx for idx, ch in enumerate(text) if ch in "{["), None)
    candidate = text[start_index:] if start_index is not None else text
    if not candidate:
        return "", None
    decoder = json.JSONDecoder()
    try:
        parsed, _ = decoder.raw_decode(candidate)
        return candidate.strip(), parsed
    except json.JSONDecodeError:
        return candidate.strip(), None


def _attach_year(parsed: object, year_tag: Optional[str]) -> object:
    """Ensure `year` is the leading key when parsed JSON is a dict or list."""
    if not year_tag:
        return parsed
    if isinstance(parsed, dict):
        remainder = {key: value for key, value in parsed.items() if key != "year"}
        ordered = {"year": year_tag}
        ordered.update(remainder)
        return ordered
    if isinstance(parsed, list):
        result = []
        for item in parsed:
            if isinstance(item, dict):
                remainder = {key: value for key, value in item.items() if key != "year"}
                ordered = {"year": year_tag}
                ordered.update(remainder)
                result.append(ordered)
            else:
                result.append(item)
        return result
    return parsed


def write_json(target: Path, payload: str, year_tag: Optional[str]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    cleaned, parsed = _extract_json_payload(payload)
    if parsed is not None:
        parsed = _attach_year(parsed, year_tag)
        target.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
        return
    fallback = cleaned or payload.strip()
    if year_tag:
        wrapped = {"year": year_tag, "raw": fallback}
        target.write_text(json.dumps(wrapped, ensure_ascii=False, indent=2), encoding="utf-8")
        return
    target.write_text(fallback, encoding="utf-8")


def process_half_page(half: HalfPage, pdf_path: Path, cfg: Config, prompt_text: str, model, year_tag: str) -> None:
    """Process a single half page: Yomitoku OCR + Gemini API call."""
    safe = safe_name(pdf_path)
    pdf_out = cfg.output_dir / safe
    page_dir = pdf_out / half.label

    html_path = run_yomitoku(half.image_path, page_dir, cfg.device, cfg.yomitoku_cmd)
    gemini_text = call_gemini(model, prompt_text, half.pdf_path, html_path)
    json_target = pdf_out / f"{pdf_path.stem}_{half.label}.json"
    write_json(json_target, gemini_text, year_tag)
    print(f"[DONE] {pdf_path.name} -> {half.label} -> {json_target}")


def process_pdf(pdf_path: Path, cfg: Config, prompt_text: str, model) -> None:
    """Process a PDF: split into halves and process them in parallel."""
    safe = safe_name(pdf_path)
    pdf_out = cfg.output_dir / safe
    halves = split_pdf(pdf_path, pdf_out)
    year_tag = pdf_path.stem

    # Process half pages in parallel
    with ThreadPoolExecutor(max_workers=cfg.max_page_workers) as executor:
        futures = {
            executor.submit(process_half_page, half, pdf_path, cfg, prompt_text, model, year_tag): half
            for half in halves
        }
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as exc:
                half = futures[future]
                print(f"[ERROR] {pdf_path.name} -> {half.label} failed: {exc}")


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="PDF -> Yomitoku HTML -> Gemini JSON pipeline")
    parser.add_argument("--pdf", type=Path, default=None, help="Single PDF override")
    parser.add_argument("--pdf-dir", type=Path, default=None, help="Directory override")
    parser.add_argument("--prompt", type=Path, default=None, help="Prompt override")
    parser.add_argument("--output", type=Path, default=None, help="Output directory override")
    parser.add_argument("--device", choices=["cpu", "cuda"], default=None)
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--yomitoku", type=Path, default=None)
    parser.add_argument("--max-workers", type=int, default=None, help="Max parallel PDFs")
    parser.add_argument("--max-page-workers", type=int, default=None, help="Max parallel pages per PDF")
    args = parser.parse_args(argv)

    cfg = resolve_config()
    if args.pdf is not None:
        cfg.pdf = args.pdf
    if args.pdf_dir is not None:
        cfg.pdf_dir = args.pdf_dir
    if args.prompt is not None:
        cfg.prompt_path = args.prompt
    if args.output is not None:
        cfg.output_dir = args.output
    if args.device is not None:
        cfg.device = args.device
    if args.model is not None:
        cfg.model = args.model
    if args.yomitoku is not None:
        cfg.yomitoku_cmd = args.yomitoku
    if args.max_workers is not None:
        cfg.max_workers = args.max_workers
    if args.max_page_workers is not None:
        cfg.max_page_workers = args.max_page_workers

    pdfs = iter_pdfs(cfg.pdf, cfg.pdf_dir)
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY must be stored in .env")

    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    prompt_text = cfg.prompt_path.read_text(encoding="utf-8")
    model = build_model(api_key, cfg.model)

    print(f"Processing {len(pdfs)} PDF(s) with max_workers={cfg.max_workers}, max_page_workers={cfg.max_page_workers}")

    # Process multiple PDFs in parallel
    with ThreadPoolExecutor(max_workers=cfg.max_workers) as executor:
        futures = {
            executor.submit(process_pdf, pdf, cfg, prompt_text, model): pdf
            for pdf in pdfs
        }
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as exc:
                pdf = futures[future]
                print(f"[ERROR] Processing {pdf.name} failed: {exc}")


if __name__ == "__main__":
    main()
