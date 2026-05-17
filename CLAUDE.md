# ReportForge PBI

ReportForge PBI is a local-first Claude Desktop MCP app for generating Power BI
`.pbit` reports.

## Supported Setup

Railway deployment is not the current target. The intended workflow is:

- Clone or download this repo locally.
- Run `setup_local.ps1`.
- Configure Claude Desktop to launch `run_mcp_stdio.ps1`.
- Use Claude Desktop MCP tools to read local CSV files and save reports locally.

## Capabilities

- Generate Power BI dashboards from local CSV files.
- Generate from pasted CSV text or base64 CSV.
- Profile CSVs for measures, dimensions, temporal columns, geographic columns,
  KPI candidates, and domain hints.
- Build semantic model JSON, Power Query M, Power BI layout JSON, theme JSON,
  and compiled `.pbit` files.
- Export local `.pbit` files into `generated_reports/`.
- Shorten generated filenames to avoid Windows/Power BI path errors.
- Apply template-based dashboard layouts:
  - KPI rail
  - KPI grid
  - central chart slots
  - right-side filter panel
  - light canvas
  - white cards
  - subtle borders
  - capped visual counts to avoid clutter
- Strip problematic generated sort metadata that caused Power BI Desktop 2026
  renderer failures.

## Anthropic API Usage

No Anthropic key is required for deterministic CSV-to-dashboard tools:

- `create_dashboard`
- `create_from_csv_file_path`
- `create_from_csv_text`
- `create_from_csv`
- `export_pbit_file`
- `get_report_state`

An Anthropic key is required for server-side LLM features:

- `create_report`
- `add_visual`
- `edit_styling`
- `apply_image_theme`
- `add_filter`

In Claude Desktop local mode, put `ANTHROPIC_API_KEY` in the MCP server `env`
block or set it as a normal Windows environment variable.

## Important Files

- `LOCAL_SETUP.md` - complete local install and Claude Desktop config.
- `setup_local.ps1` - creates venv and installs Python requirements.
- `run_mcp_stdio.ps1` - Claude Desktop stdio entrypoint.
- `run_api.ps1` - optional local FastAPI entrypoint.
- `mcp_server.py` - MCP tool definitions.
- `auto_intent.py` - deterministic CSV dashboard generation.
- `file_writer.py` - Power BI project and PBIT writer.
- `prompts/` - prompt files for Anthropic-powered features.
