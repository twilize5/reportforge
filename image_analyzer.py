import anthropic, json

client = anthropic.Anthropic()

IMAGE_PALETTE_SYSTEM = """
Analyze this dashboard image and extract its visual design system.
Return ONLY valid JSON with this exact shape:

{
  "primary": "#2D5BFF",
  "secondary": "#1A3A8F",
  "accent": "#FF6B35",
  "background": "#FFFFFF",
  "text": "#252423",
  "data_colors": ["#2D5BFF", "#FF6B35", "#28C76F", "#EA5455", "#FF9F43", "#1E9AF5", "#9B59B6", "#2ECC71"],
  "style_notes": "dark navy header, minimal gridlines, rounded cards, sans-serif font",
  "chart_style": "flat",
  "border_radius": "soft"
}

data_colors: 8 hex values representing the chart series palette visible in the image.
Extract the ACTUAL colors from the image — do not invent colors not present.
style_notes: brief description of the overall aesthetic.
chart_style: flat | gradient | outlined | shadowed
border_radius: none | soft | rounded
"""

def extract_palette_from_image(image_base64: str, media_type: str = "image/png") -> dict:
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=800,
        system=IMAGE_PALETTE_SYSTEM,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_base64
                    }
                },
                {
                    "type": "text",
                    "text": "Extract the color palette and style from this dashboard."
                }
            ]
        }]
    )
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(raw)
