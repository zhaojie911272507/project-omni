"""File processing tools for Project Omni.

PDF parsing, CSV analysis, and image understanding (Vision).
"""

from __future__ import annotations

import base64
import io
import json
import os
from pathlib import Path
from typing import Any

import pandas as pd
from PIL import Image

from agent import tool


# ─────────────────────────────────────────────────────────────────────────────
# PDF Processing
# ─────────────────────────────────────────────────────────────────────────────


@tool(
    name="read_pdf",
    description=(
        "Extract text content from a PDF file. "
        "Returns the full text content or a specific page range."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the PDF file"},
            "pages": {
                "type": "string",
                "description": "Page range to extract (e.g., '1-5', '1,3,5'). Default: all pages",
            },
            "max_pages": {
                "type": "integer",
                "description": "Maximum number of pages to extract. Default: 50",
            },
        },
        "required": ["path"],
    },
)
def read_pdf(path: str, pages: str | None = None, max_pages: int = 50) -> str:
    """Extract text from PDF file."""
    try:
        import pymupdf
    except ImportError:
        return "[error] PyMuPDF not installed. Run: pip install pymupdf"

    if not os.path.exists(path):
        return f"[error] File not found: {path}"

    try:
        doc = pymupdf.open(path)
        num_pages = len(doc)

        # Parse page range
        page_indices: list[int] = []
        if pages:
            for part in pages.split(","):
                part = part.strip()
                if "-" in part:
                    start, end = part.split("-")
                    page_indices.extend(range(int(start) - 1, int(end)))
                else:
                    page_indices.append(int(part) - 1)
        else:
            page_indices = list(range(min(num_pages, max_pages)))

        results: list[str] = []
        for i in page_indices:
            if 0 <= i < num_pages:
                page = doc[i]
                text = page.get_text()
                if text.strip():
                    results.append(f"--- Page {i + 1} ---\n{text}")

        doc.close()

        if not results:
            return "[error] No text found in PDF"

        output = "\n\n".join(results)
        return f"[extracted {len(page_indices)} pages, {len(output)} chars]\n\n{output}"

    except Exception as exc:  # noqa: BLE001
        return f"[error] {exc}"


@tool(
    name="pdf_info",
    description="Get metadata and information about a PDF file.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the PDF file"},
        },
        "required": ["path"],
    },
)
def pdf_info(path: str) -> str:
    """Get PDF metadata."""
    try:
        import pymupdf
    except ImportError:
        return "[error] PyMuPDF not installed. Run: pip install pymupdf"

    if not os.path.exists(path):
        return f"[error] File not found: {path}"

    try:
        doc = pymupdf.open(path)
        info = {
            "pages": len(doc),
            "title": doc.metadata.get("title", ""),
            "author": doc.metadata.get("author", ""),
            "subject": doc.metadata.get("subject", ""),
            "creator": doc.metadata.get("creator", ""),
            "producer": doc.metadata.get("producer", ""),
            "encrypted": doc.is_encrypted,
        }
        doc.close()
        return json.dumps(info, indent=2)
    except Exception as exc:  # noqa: BLE001
        return f"[error] {exc}"


# ─────────────────────────────────────────────────────────────────────────────
# CSV Processing
# ─────────────────────────────────────────────────────────────────────────────


@tool(
    name="analyze_csv",
    description=(
        "Analyze a CSV file and return statistics, structure, or filtered data. "
        "Can show schema, summary stats, or specific rows."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the CSV file"},
            "mode": {
                "type": "string",
                "description": "Analysis mode: 'schema', 'head', 'tail', 'stats', 'filter'",
                "enum": ["schema", "head", "tail", "stats", "filter"],
            },
            "rows": {
                "type": "integer",
                "description": "Number of rows to show (for head/tail). Default: 10",
            },
            "filter_column": {
                "type": "string",
                "description": "Column to filter by (for filter mode)",
            },
            "filter_value": {
                "type": "string",
                "description": "Value to filter by (for filter mode)",
            },
        },
        "required": ["path", "mode"],
    },
)
def analyze_csv(
    path: str,
    mode: str = "schema",
    rows: int = 10,
    filter_column: str | None = None,
    filter_value: str | None = None,
) -> str:
    """Analyze CSV file."""
    if not os.path.exists(path):
        return f"[error] File not found: {path}"

    try:
        df = pd.read_csv(path)

        if mode == "schema":
            info = {
                "columns": list(df.columns),
                "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
                "shape": list(df.shape),
                "null_counts": {col: int(count) for col, count in df.isnull().sum().items()},
            }
            return json.dumps(info, indent=2, ensure_ascii=False)

        elif mode == "head":
            return df.head(rows).to_string()

        elif mode == "tail":
            return df.tail(rows).to_string()

        elif mode == "stats":
            return df.describe().to_string()

        elif mode == "filter":
            if not filter_column or filter_value is None:
                return "[error] filter_column and filter_value required for filter mode"
            if filter_column not in df.columns:
                return f"[error] Column '{filter_column}' not found"
            filtered = df[df[filter_column].astype(str).str.contains(filter_value, case=False, na=False)]
            return f"[found {len(filtered)} rows]\n\n{filtered.to_string()}"

        return "[error] Unknown mode"

    except Exception as exc:  # noqa: BLE001
        return f"[error] {exc}"


@tool(
    name="csv_to_json",
    description="Convert CSV file to JSON format.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the CSV file"},
            "orient": {
                "type": "string",
                "description": "JSON orientation: 'records', 'index', 'columns'",
                "enum": ["records", "index", "columns"],
            },
            "limit": {
                "type": "integer",
                "description": "Limit number of rows. Default: all",
            },
        },
        "required": ["path"],
    },
)
def csv_to_json(path: str, orient: str = "records", limit: int | None = None) -> str:
    """Convert CSV to JSON."""
    if not os.path.exists(path):
        return f"[error] File not found: {path}"

    try:
        df = pd.read_csv(path)
        if limit:
            df = df.head(limit)
        return df.to_json(orient=orient, force_ascii=False, indent=2)
    except Exception as exc:  # noqa: BLE001
        return f"[error] {exc}"


# ─────────────────────────────────────────────────────────────────────────────
# Image Processing (Vision)
# ─────────────────────────────────────────────────────────────────────────────


@tool(
    name="analyze_image",
    description=(
        "Analyze an image file and describe its contents using AI vision. "
        "Supports JPEG, PNG, GIF, BMP, WEBP formats."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the image file"},
            "detail": {
                "type": "string",
                "description": "Analysis detail level: 'low', 'high'",
                "enum": ["low", "high"],
            },
        },
        "required": ["path"],
    },
)
def analyze_image(path: str, detail: str = "low") -> str:
    """Analyze image using AI vision."""
    if not os.path.exists(path):
        return f"[error] File not found: {path}"

    try:
        # Read and validate image
        img = Image.open(path)
        if img.format not in ("JPEG", "PNG", "GIF", "BMP", "WEBP"):
            return f"[error] Unsupported image format: {img.format}"

        # Convert to base64
        buffered = io.BytesIO()
        img.save(buffered, format=img.format or "PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode()

        # Use LiteLLM with vision-capable model
        import litellm

        model = os.getenv("OMNI_MODEL", "gpt-4o-mini")

        # Use a vision-capable model
        if "gpt-4o" in model or "gpt-4" in model or "claude-3" in model:
            vision_model = model
        else:
            vision_model = "gpt-4o-mini"

        prompt = (
            "Describe this image in detail. Include:"
            "\n- What you see (objects, people, scene)"
            "\n- Colors and visual style"
            "\n- Any text visible in the image"
            "\n- Your interpretation of the image"
        ) if detail == "high" else "Briefly describe what you see in this image."

        response = litellm.completion(
            model=vision_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/{img.format.lower()};base64,{img_b64}",
                                "detail": detail,
                            },
                        },
                    ],
                }
            ],
        )

        return response.choices[0].message.content or "[no response]"

    except ImportError:
        return "[error] litellm not installed. Run: pip install litellm"
    except Exception as exc:  # noqa: BLE001
        return f"[error] {exc}"


@tool(
    name="image_info",
    description="Get image metadata (dimensions, format, mode, size).",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the image file"},
        },
        "required": ["path"],
    },
)
def image_info(path: str) -> str:
    """Get image metadata."""
    if not os.path.exists(path):
        return f"[error] File not found: {path}"

    try:
        img = Image.open(path)
        info = {
            "format": img.format,
            "mode": img.mode,
            "size": img.size,
            "width": img.width,
            "height": img.height,
            "file_size_bytes": os.path.getsize(path),
        }
        # Get EXIF data if available
        if hasattr(img, "_getexif") and img._getexif():
            info["has_exif"] = True
        return json.dumps(info, indent=2)
    except Exception as exc:  # noqa: BLE001
        return f"[error] {exc}"


# ─────────────────────────────────────────────────────────────────────────────
# General File Operations
# ─────────────────────────────────────────────────────────────────────────────


@tool(
    name="list_files",
    description="List files in a directory with optional filtering.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Directory path"},
            "pattern": {
                "type": "string",
                "description": "Glob pattern to filter (e.g., '*.pdf', '*.csv')",
            },
            "recursive": {
                "type": "boolean",
                "description": "Search recursively. Default: false",
            },
        },
        "required": ["path"],
    },
)
def list_files(path: str, pattern: str | None = None, recursive: bool = False) -> str:
    """List files in a directory."""
    if not os.path.exists(path):
        return f"[error] Directory not found: {path}"

    if not os.path.isdir(path):
        return f"[error] Not a directory: {path}"

    try:
        p = Path(path)

        if recursive:
            if pattern:
                files = list(p.rglob(pattern))
            else:
                files = list(p.rglob("*"))
        else:
            if pattern:
                files = list(p.glob(pattern))
            else:
                files = list(p.iterdir())

        # Filter to files only
        files = [f for f in files if f.is_file()]

        if not files:
            return "[no files found]"

        # Sort by modification time
        files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

        results: list[str] = []
        for f in files[:100]:  # Limit to 100
            size = f.stat().st_size
            size_str = f"{size / 1024:.1f} KB" if size > 1024 else f"{size} B"
            results.append(f"{f.name} ({size_str})")

        return "\n".join(results)

    except Exception as exc:  # noqa: BLE001
        return f"[error] {exc}"


@tool(
    name="file_info",
    description="Get detailed file information (size, dates, type).",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path"},
        },
        "required": ["path"],
    },
)
def file_info(path: str) -> str:
    """Get detailed file information."""
    if not os.path.exists(path):
        return f"[error] File not found: {path}"

    try:
        stat = os.stat(path)
        info = {
            "path": os.path.abspath(path),
            "name": os.path.basename(path),
            "size_bytes": stat.st_size,
            "size_formatted": f"{stat.st_size / 1024 / 1024:.2f} MB" if stat.st_size > 1024 * 1024 else f"{stat.st_size / 1024:.2f} KB",
            "is_file": os.path.isfile(path),
            "is_dir": os.path.isdir(path),
            "modified": str(stat.st_mtime),
            "created": str(stat.st_ctime),
            "extension": os.path.splitext(path)[1],
        }
        return json.dumps(info, indent=2)
    except Exception as exc:  # noqa: BLE001
        return f"[error] {exc}"