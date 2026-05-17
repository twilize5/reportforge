import json
from pathlib import Path
import anthropic

client = anthropic.Anthropic()
MODEL = "claude-sonnet-4-20250514"
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def _prompt(name: str, fallback: str) -> str:
    path = PROMPTS_DIR / name
    return path.read_text(encoding="utf-8") if path.exists() else fallback

def _call(system: str, user: str, max_tokens: int = 4000) -> dict | list:
    response = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}]
    )
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(raw)


# ── Call 1: intent extraction ─────────────────────────────────────────────────

INTENT_SYSTEM = """
Extract structured intent from a Power BI report request.
Return ONLY valid JSON — no markdown, no explanation.

Shape:
{
  "report_title": "Sales Overview",
  "tables": [
    {
      "name": "Sales",
      "columns": [
        {"name": "Date", "type": "dateTime"},
        {"name": "Region", "type": "string"},
        {"name": "Revenue", "type": "decimal"}
      ]
    }
  ],
  "measures": [
    {"name": "Total Revenue", "table": "Sales", "dax": "SUM(Sales[Revenue])", "format": "$#,0.00"}
  ],
  "relationships": [
    {"from_table": "Sales", "from_col": "Date", "to_table": "Date", "to_col": "DateKey"}
  ],
  "pages": [
    {
      "name": "Overview",
      "display_name": "Overview",
      "visuals": [
        {"type": "columnChart", "title": "Revenue by Region", "x_axis": "Sales[Region]", "y_axis": "Total Revenue"},
        {"type": "card", "title": "Total Revenue", "value": "Total Revenue"},
        {"type": "slicer", "field": "Date[Year]", "title": "Year"}
      ]
    }
  ]
}

Supported visual types: columnChart barChart lineChart areaChart pieChart
donutChart card multiRowCard tableEx matrix slicer funnel waterfall
Infer sensible tables and measures even when the prompt is vague.
"""

def extract_intent(prompt: str, schema_hint: str = "") -> dict:
    return _call(INTENT_SYSTEM,
        f"Report request: {prompt}\n\nSchema hint:\n{schema_hint}", 2000)


# ── Call 2: BIM JSON ──────────────────────────────────────────────────────────

BIM_SYSTEM = """
Generate a Power BI tabular model BIM (database.bim) JSON.

CRITICAL:
- "compatibilityLevel" MUST be 1550
- "name" MUST be "SemanticModel"
- Every partition source "expression" MUST exactly match the table name (case-sensitive)
- "crossFilteringBehavior" MUST be "oneDirection" — NEVER use "bothDirections" (causes cyclic dependency errors in Power BI Desktop)
- Return ONLY valid JSON — no markdown

Structure:
{
  "name": "SemanticModel",
  "compatibilityLevel": 1550,
  "model": {
    "culture": "en-US",
    "defaultPowerBIDataSourceVersion": "powerBI_V3",
    "tables": [
      {
        "name": "Sales",
        "columns": [
          {"name": "Date", "dataType": "dateTime", "sourceColumn": "Date"},
          {"name": "Revenue", "dataType": "decimal", "sourceColumn": "Revenue"}
        ],
        "measures": [
          {"name": "Total Revenue", "expression": "SUM(Sales[Revenue])", "formatString": "$#,0.00"}
        ],
        "partitions": [
          {"name": "Sales", "mode": "import",
           "source": {"type": "m", "expression": "Sales"}}
        ]
      }
    ],
    "relationships": [
      {
        "name": "Sales_Date",
        "fromTable": "Sales", "fromColumn": "Date",
        "toTable": "Date", "toColumn": "DateKey",
        "crossFilteringBehavior": "oneDirection"
      }
    ],
    "annotations": [{"name": "PBIDesktopVersion", "value": "2.130.0.0"}]
  }
}
"""

def generate_bim(intent: dict) -> dict:
    return _call(BIM_SYSTEM,
        f"Generate BIM for:\n{json.dumps(intent, indent=2)}", 4000)


# ── Call 3: M queries ─────────────────────────────────────────────────────────

M_SYSTEM = """
Generate Power Query M expressions for Power BI tables.
Return ONLY JSON: {"TableName": "M expression", ...}
Table names must EXACTLY match those given (case-sensitive).
Each value is the M expression only — NOT the "shared #..." wrapper.
Use placeholder paths like "placeholder.csv".
Always end with Table.TransformColumnTypes with correct types.
No markdown. No explanation.
"""

def generate_m_queries(intent: dict, schema_hint: str = "") -> dict:
    table_names = [t["name"] for t in intent["tables"]]
    return _call(M_SYSTEM,
        f"Tables (use EXACTLY these names): {json.dumps(table_names)}\n"
        f"Columns: {json.dumps(intent['tables'], indent=2)}\n"
        f"Schema: {schema_hint or 'not provided'}", 3000)


# ── Call 4: Layout JSON ───────────────────────────────────────────────────────

LAYOUT_SYSTEM = _prompt("layout.txt", """
Generate Power BI report layout JSON for pbi-tools section files.

CRITICAL: config, filters, query, dataTransforms MUST be JSON-encoded strings
(double-serialized) — NOT nested objects. e.g.:
  "config": "{\\"singleVisual\\":{\\"visualType\\":\\"columnChart\\"}}"
  NOT: "config": {"singleVisual": ...}

Page canvas: width=1280, height=720. 20px margins. 16px gaps between visuals.
Return ONLY valid JSON:
{
  "pages": [
    {
      "name": "Overview",
      "displayName": "Overview",
      "width": 1280,
      "height": 720,
      "visualContainers": [
        {
          "x": 20, "y": 20, "width": 600, "height": 320,
          "config": "{\\"singleVisual\\":{\\"visualType\\":\\"columnChart\\",...}}",
          "filters": "[]",
          "query": "{}",
          "dataTransforms": "{}"
        }
      ]
    }
  ]
}
""")

def generate_layout(intent: dict) -> dict:
    return _call(LAYOUT_SYSTEM,
        f"Pages: {json.dumps(intent.get('pages', []), indent=2)}\n"
        f"Measures: {[m['name'] for m in intent.get('measures', [])]}\n"
        f"Tables: {[(t['name'], [c['name'] for c in t['columns']]) for t in intent.get('tables', [])]}",
        4000)


# ── Call 5: add or edit a visual (for iterative editing) ─────────────────────

VISUAL_EDIT_SYSTEM = _prompt("visual_edit.txt", """
You modify or add visuals to an existing Power BI report layout.
Given the current page JSON and an edit instruction, return the UPDATED page JSON.
Rules:
- Preserve all existing visuals unless explicitly told to remove one
- New visuals: position them in empty space, snap to 12px grid
- config/filters/query/dataTransforms MUST remain JSON-encoded strings
- Return ONLY the updated page JSON — no markdown, no explanation
""")

def apply_visual_edit(page_json: dict, instruction: str) -> dict:
    return _call(VISUAL_EDIT_SYSTEM,
        f"Instruction: {instruction}\n\n"
        f"Current page:\n{json.dumps(page_json, indent=2)}", 4000)


# ── Call 6: styling edit ──────────────────────────────────────────────────────

STYLE_EDIT_SYSTEM = """
You apply styling changes to a Power BI theme JSON.
Given the current theme and an instruction, return the updated theme JSON.
Only change what the instruction specifies — preserve everything else.
Return ONLY valid JSON — no markdown.
"""

def apply_style_edit(theme_json: dict, instruction: str) -> dict:
    return _call(STYLE_EDIT_SYSTEM,
        f"Instruction: {instruction}\n\n"
        f"Current theme:\n{json.dumps(theme_json, indent=2)}", 1500)
