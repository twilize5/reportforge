import base64
import os
import re
import shutil
from pathlib import Path
from fastmcp import FastMCP
from orchestrator import (pipeline_create, pipeline_add_visual,
                           pipeline_apply_theme, pipeline_edit_style,
                           pipeline_add_filter, pipeline_export,
                           pipeline_from_csv)
from session_manager import require_session

mcp = FastMCP("ReportForge PBI")

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "/tmp/reportforge_reports"))
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")


def _safe_filename(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_. -]", "_", name).strip()
    return safe or "report"


def _save_report_copy(state, suffix: str = "pbit") -> str:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    title = state.intent.report_title if state.intent else "report"
    filename = f"{_safe_filename(title)}_{state.session_id[:8]}.{suffix}"
    output_path = OUTPUT_DIR / filename
    shutil.copyfile(state.pbix_path, output_path)
    return str(output_path.resolve())


def _download_url(file_path: str) -> str | None:
    if not PUBLIC_BASE_URL:
        return None
    return f"{PUBLIC_BASE_URL}/reports/{Path(file_path).name}"

@mcp.tool()
async def create_dashboard(
    dataset_path: str,
    title: str = "",
) -> dict:
    """
    Create a complete Power BI dashboard from a local dataset path.
    USE THIS TOOL when the user says "create a dashboard/report from this dataset"
    and provides a local file path. Prefer this over create_report because this
    reads real data rows and does not require an Anthropic API key.

    Supports CSV files. Returns a local .pbit file_path, not base64.
    """
    return await create_from_csv_file_path(dataset_path, title)


@mcp.tool()
async def create_report(description: str) -> dict:
    """
    Create a new Power BI report from a natural language description.
    Do NOT use this when the user provides a CSV/dataset file path; use
    create_dashboard instead. This tool needs a valid Anthropic API key.
    Returns a session_id to use in all subsequent tool calls.
    Example: "monthly sales by region with YoY comparison for retail team"
    """
    state = await pipeline_create(description)
    return {
        "session_id": state.session_id,
        "report_title": state.intent.report_title if state.intent else "",
        "tables": [t.name for t in (state.intent.tables if state.intent else [])],
        "pages": [p.name for p in (state.intent.pages if state.intent else [])],
        "message": "Report created. Use export_pbix to download."
    }


@mcp.tool()
async def add_visual(session_id: str, description: str,
                     page_name: str = "Overview") -> dict:
    """
    Add a visual to an existing report session.
    description: plain English e.g. "bar chart of units sold by product category"
    page_name: which page to add to (default: Overview)
    """
    state = await pipeline_add_visual(session_id, description, page_name)
    return {
        "session_id": session_id,
        "visual_added": description,
        "page": page_name,
        "message": "Visual added. Use export_pbix to download updated report."
    }


@mcp.tool()
async def apply_image_theme(session_id: str, image_base64: str,
                             media_type: str = "image/png") -> dict:
    """
    Extract color palette from a dashboard image and apply it as the report theme.
    image_base64: base64-encoded image string
    media_type: image/png or image/jpeg
    """
    state = await pipeline_apply_theme(session_id, image_base64, media_type)
    return {
        "session_id": session_id,
        "colors_extracted": state.palette.data_colors if state.palette else [],
        "primary_color": state.palette.primary if state.palette else None,
        "message": "Theme applied. Use export_pbix to download."
    }


@mcp.tool()
async def edit_styling(session_id: str, instruction: str) -> dict:
    """
    Edit report styling via natural language.
    Examples:
    - "make all charts use a dark navy background"
    - "change primary color to #FF5733"
    - "use a minimal flat style with no borders"
    """
    state = await pipeline_edit_style(session_id, instruction)
    return {
        "session_id": session_id,
        "instruction_applied": instruction,
        "message": "Styling updated. Use export_pbix to download."
    }


@mcp.tool()
async def add_filter(session_id: str, filter_description: str,
                     page_name: str = None) -> dict:
    """
    Add a slicer or filter to the report.
    Examples:
    - "add a Year slicer to the Overview page"
    - "add a Region dropdown filter"
    - "add a date range filter for all pages"
    page_name: specific page, or None for all pages
    """
    state = await pipeline_add_filter(session_id, filter_description, page_name)
    return {
        "session_id": session_id,
        "filter_added": filter_description,
        "message": "Filter added. Use export_pbix to download."
    }


@mcp.tool()
async def export_pbix(session_id: str) -> dict:
    """
    Compile the current session into a .pbix file and return it as base64.
    The base64 string can be decoded and saved as report.pbix.
    """
    state, pbix_path = await pipeline_export(session_id)
    with open(pbix_path, "rb") as f:
        pbix_bytes = f.read()
    return {
        "session_id": session_id,
        "file_size_kb": round(len(pbix_bytes) / 1024, 1),
        "pbix_base64": base64.b64encode(pbix_bytes).decode(),
        "filename": f"{state.intent.report_title if state.intent else 'report'}.pbix",
        "message": "Decode base64 and save as .pbix to open in Power BI Desktop."
    }


@mcp.tool()
async def export_pbit_file(session_id: str) -> dict:
    """
    Compile the current session and save the .pbit locally.
    Claude Desktop should prefer this over export_pbix to avoid huge base64 output.
    """
    state, pbix_path = await pipeline_export(session_id)
    state.pbix_path = pbix_path
    output_path = _save_report_copy(state, "pbit")
    return {
        "session_id": session_id,
        "file_path": output_path,
        "download_url": _download_url(output_path),
        "filename": Path(output_path).name,
        "message": "Report saved. On Railway, use download_url; locally, open file_path in Power BI Desktop.",
    }


@mcp.tool()
async def export_pbit_url(session_id: str) -> dict:
    """
    Compile the current session, save the .pbit on the hosted server, and return
    a public download URL. Set PUBLIC_BASE_URL on Railway for this tool.
    """
    state, pbix_path = await pipeline_export(session_id)
    state.pbix_path = pbix_path
    output_path = _save_report_copy(state, "pbit")
    url = _download_url(output_path)
    if not url:
        return {
            "session_id": session_id,
            "filename": Path(output_path).name,
            "file_path": output_path,
            "error": "PUBLIC_BASE_URL is not set.",
            "message": "Set PUBLIC_BASE_URL to your Railway public domain, then redeploy.",
        }
    return {
        "session_id": session_id,
        "filename": Path(output_path).name,
        "download_url": url,
        "message": "Download the .pbit from download_url and open it in Power BI Desktop.",
    }


@mcp.tool()
async def create_from_csv(
    csv_base64: str,
    filename: str = "data.csv",
    prompt: str = "",
    image_base64: str = "",
) -> dict:
    """
    Create a Power BI dashboard from a CSV file.
    Auto-generates KPI cards, bar chart, line chart, pie chart, and slicer — no prompt required.
    csv_base64: base64-encoded CSV bytes.
    filename: original filename (used for table naming in the data model).
    prompt: optional report title override (e.g. "Q4 Sales Overview").
    image_base64: optional branding image (base64) to extract theme colors from.
    Returns: session_id, pbix_base64 (save as .pbit), report_title, columns_detected, domain.
    """
    csv_bytes = base64.b64decode(csv_base64)
    img_b64 = image_base64 if image_base64 else None
    state = await pipeline_from_csv(csv_bytes, filename, prompt, img_b64)
    with open(state.pbix_path, "rb") as f:
        pbix_b64 = base64.b64encode(f.read()).decode()
    profile = state.dataset_profile
    return {
        "session_id": state.session_id,
        "pbix_base64": pbix_b64,
        "filename": f"{state.intent.report_title if state.intent else filename}.pbit",
        "report_title": state.intent.report_title if state.intent else filename,
        "columns_detected": len(profile.columns) if profile else 0,
        "measures_found": profile.measures if profile else [],
        "domain": profile.domain_hint if profile else "general",
        "message": "Decode pbix_base64 and save as .pbit to open in Power BI Desktop.",
    }


@mcp.tool()
async def create_from_csv_text(
    csv_text: str,
    filename: str = "data.csv",
    prompt: str = "",
) -> dict:
    """
    Create a Power BI dashboard from raw CSV text.
    This is easier to use from Claude Desktop than base64 input.
    Does not require an Anthropic API key unless image theming is used elsewhere.
    """
    state = await pipeline_from_csv(
        csv_text.encode("utf-8-sig"),
        filename,
        prompt,
        None,
    )
    if state.dataset_profile and state.dataset_profile.row_count == 0:
        return {
            "session_id": state.session_id,
            "error": "CSV text contains headers but no data rows.",
            "message": "Use create_from_csv_file_path with the real CSV file path, or paste CSV text including data rows.",
        }
    output_path = _save_report_copy(state, "pbit")
    profile = state.dataset_profile
    return {
        "session_id": state.session_id,
        "file_path": output_path,
        "download_url": _download_url(output_path),
        "filename": Path(output_path).name,
        "report_title": state.intent.report_title if state.intent else filename,
        "columns_detected": len(profile.columns) if profile else 0,
        "measures_found": profile.measures if profile else [],
        "domain": profile.domain_hint if profile else "general",
        "message": "Report saved. On Railway, use download_url; locally, open file_path in Power BI Desktop.",
    }


@mcp.tool()
async def create_from_csv_file_path(
    file_path: str,
    prompt: str = "",
) -> dict:
    """
    Create a Power BI dashboard from a CSV file already on this computer.
    Preferred for Claude Desktop because it avoids putting large CSV/base64 data
    into the conversation context.
    """
    csv_path = Path(file_path).expanduser().resolve()
    if not csv_path.exists():
        return {
            "error": f"CSV file not found: {csv_path}",
            "message": "Pass an absolute path to an existing .csv file.",
        }
    if csv_path.suffix.lower() != ".csv":
        return {
            "error": f"Expected a .csv file, got: {csv_path.name}",
            "message": "Pass an absolute path to a CSV file.",
        }

    csv_bytes = csv_path.read_bytes()
    state = await pipeline_from_csv(
        csv_bytes,
        csv_path.name,
        prompt,
        None,
    )
    output_path = _save_report_copy(state, "pbit")
    profile = state.dataset_profile
    return {
        "session_id": state.session_id,
        "file_path": output_path,
        "download_url": _download_url(output_path),
        "filename": Path(output_path).name,
        "report_title": state.intent.report_title if state.intent else csv_path.stem,
        "row_count": profile.row_count if profile else 0,
        "columns_detected": len(profile.columns) if profile else 0,
        "measures_found": [m.name for m in state.intent.measures] if state.intent else [],
        "dimensions_found": [c.name for t in state.intent.tables for c in t.columns] if state.intent else [],
        "domain": profile.domain_hint if profile else "general",
        "message": "Report saved. On Railway, use download_url; locally, open file_path in Power BI Desktop.",
    }


@mcp.tool()
async def get_report_state(session_id: str) -> dict:
    """
    Return the current report structure for inspection.
    Useful for understanding what has been generated before editing.
    """
    state = require_session(session_id)
    return {
        "session_id": session_id,
        "report_title": state.intent.report_title if state.intent else None,
        "tables": [t.name for t in (state.intent.tables if state.intent else [])],
        "measures": [m.name for m in (state.intent.measures if state.intent else [])],
        "pages": [p.name for p in (state.intent.pages if state.intent else [])],
        "has_theme": state.theme is not None,
        "palette_colors": state.palette.data_colors if state.palette else [],
        "edit_history": state.history,
        "pbix_compiled": state.pbix_path is not None
    }
