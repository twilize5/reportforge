import base64
import re
from pathlib import Path
from fastapi import FastAPI, UploadFile, Form, File
from fastapi import HTTPException
from fastapi.responses import FileResponse, JSONResponse
from orchestrator import (pipeline_create, pipeline_add_visual,
                           pipeline_apply_theme, pipeline_edit_style,
                           pipeline_add_filter, pipeline_export,
                           pipeline_from_csv)
from session_manager import require_session
from mcp_server import mcp, OUTPUT_DIR


def _safe_filename(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_. -]", "_", name).strip()
    return safe or "report"

# Build MCP ASGI sub-app first so we can pass its lifespan to FastAPI
# fastmcp 3.x requires the parent app's lifespan to include the MCP lifespan
_mcp_asgi = mcp.http_app(path="/")

app = FastAPI(
    title="ReportForge PBI",
    description="Power BI .pbix generator with image theming, NL editing, and MCP support",
    version="1.0.0",
    lifespan=_mcp_asgi.lifespan,
)

# Mount MCP server at /mcp
app.mount("/mcp", _mcp_asgi)

@app.get("/health")
def health():
    return {"status": "ok", "service": "ReportForge PBI"}


@app.get("/reports/{filename}")
def download_report(filename: str):
    safe_name = Path(filename).name
    report_path = (OUTPUT_DIR / safe_name).resolve()
    output_root = OUTPUT_DIR.resolve()
    if output_root not in report_path.parents and report_path != output_root:
        raise HTTPException(status_code=400, detail="Invalid report path")
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Report not found or expired")
    return FileResponse(
        report_path,
        media_type="application/octet-stream",
        filename=safe_name,
    )

@app.post("/generate")
async def generate(
    prompt: str = Form(...),
    schema_file: UploadFile = File(None),
    image_file: UploadFile = File(None)
):
    schema_hint = ""
    if schema_file:
        schema_hint = (await schema_file.read()).decode(errors="replace")[:4000]

    image_base64 = None
    media_type = "image/png"
    if image_file:
        img_bytes = await image_file.read()
        image_base64 = base64.b64encode(img_bytes).decode()
        media_type = image_file.content_type or "image/png"

    state = await pipeline_create(prompt, schema_hint, image_base64, media_type)
    return FileResponse(
        state.pbix_path,
        media_type="application/octet-stream",
        filename=f"{state.intent.report_title}.pbit"
    )

@app.post("/session/{session_id}/add-visual")
async def add_visual(session_id: str, description: str = Form(...),
                     page_name: str = Form("Overview")):
    state = await pipeline_add_visual(session_id, description, page_name)
    return {"session_id": session_id, "status": "visual added"}

@app.post("/session/{session_id}/theme")
async def apply_theme(session_id: str, image_file: UploadFile = File(...)):
    img_bytes = await image_file.read()
    image_base64 = base64.b64encode(img_bytes).decode()
    state = await pipeline_apply_theme(
        session_id, image_base64, image_file.content_type or "image/png"
    )
    return {"session_id": session_id, "colors": state.palette.data_colors}

@app.post("/session/{session_id}/style")
async def edit_style(session_id: str, instruction: str = Form(...)):
    state = await pipeline_edit_style(session_id, instruction)
    return {"session_id": session_id, "status": "styling updated"}

@app.post("/session/{session_id}/filter")
async def add_filter(session_id: str, filter_description: str = Form(...),
                     page_name: str = Form(None)):
    state = await pipeline_add_filter(session_id, filter_description, page_name)
    return {"session_id": session_id, "status": "filter added"}

@app.get("/session/{session_id}/export")
async def export(session_id: str):
    state, pbix_path = await pipeline_export(session_id)
    return FileResponse(
        pbix_path,
        media_type="application/octet-stream",
        filename=f"{state.intent.report_title if state.intent else 'report'}.pbit"
    )

@app.post("/generate-from-csv")
async def generate_from_csv(
    csv_file: UploadFile = File(...),
    prompt: str = Form(""),
    image_file: UploadFile = File(None)
):
    csv_bytes = await csv_file.read()
    image_base64 = None
    media_type = "image/png"
    if image_file:
        img_bytes = await image_file.read()
        image_base64 = base64.b64encode(img_bytes).decode()
        media_type = image_file.content_type or "image/png"
    state = await pipeline_from_csv(
        csv_bytes, csv_file.filename or "data.csv",
        prompt, image_base64, media_type
    )
    # Keep a public copy for remote MCP/Railway workflows.
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    title = state.intent.report_title if state.intent else "report"
    public_path = OUTPUT_DIR / f"{_safe_filename(title)}_{state.session_id[:8]}.pbit"
    public_path.write_bytes(Path(state.pbix_path).read_bytes())
    return FileResponse(
        state.pbix_path,
        media_type="application/octet-stream",
        filename=f"{state.intent.report_title}.pbit"
    )


@app.get("/session/{session_id}/state")
def get_state(session_id: str):
    state = require_session(session_id)
    return JSONResponse(state.model_dump(exclude={"bim", "m_code", "layout"}))
