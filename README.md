# ReportForge PBI

Local Claude Desktop MCP app for generating Power BI `.pbit` reports from CSV
datasets, natural-language instructions, and reference-image styling.

The recommended setup is local stdio MCP. Claude Desktop runs this project on
your machine, so the MCP can read local CSV files and save generated reports
back to `generated_reports/`.

## Capabilities

- Create a Power BI dashboard from a local CSV path.
- Create a dashboard from pasted CSV text or base64 CSV.
- Profile CSV columns and infer KPIs, dimensions, measures, date fields, and slicers.
- Generate a Power BI semantic model, Power Query M, report layout, theme, and `.pbit`.
- Apply template-based layouts inspired by the reference dashboard images:
  KPI rail/grid, central chart panels, right filter panel, light canvas, white cards,
  subtle borders, and capped visual counts to avoid clutter.
- Export a local `.pbit` file for Power BI Desktop.
- Optional Anthropic-powered features for natural-language report creation,
  visual edits, styling edits, and image theme extraction.

## Quick Start

```powershell
git clone https://github.com/twilize5/reportforge.git
cd reportforge
.\setup_local.ps1
```

Then install `pbi-tools.core` and configure Claude Desktop using
`LOCAL_SETUP.md`.

## Main Files

- `mcp_server.py` - MCP tools exposed to Claude Desktop.
- `mcp_stdio.py` - stdio entrypoint for Claude Desktop.
- `main.py` - optional local FastAPI server.
- `auto_intent.py` - deterministic CSV profiling to dashboard generation.
- `file_writer.py` - writes Power BI project files and injects DataMashup/layout.
- `prompts/` - prompts for Anthropic-powered paths.
- `setup_local.ps1` - creates local venv and installs Python dependencies.
- `run_mcp_stdio.ps1` - starts the MCP stdio server.
- `run_api.ps1` - starts optional local HTTP API on port 8000.

## Docs

- `LOCAL_SETUP.md` - local installation and Claude Desktop configuration.
- `CLAUDE.md` - project knowledge and capability notes.
