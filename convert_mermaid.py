"""
Mermaid diagram converter using Playwright.
Reads .md files from input/, extracts mermaid code blocks, renders them
as PNG images using a headless browser, and saves to output/.

Optional: Set ANTHROPIC_API_KEY in your environment to get AI-generated
descriptions for each diagram (saved as a companion .txt file).
"""

import os
import re
import sys
import textwrap
from pathlib import Path

from playwright.sync_api import sync_playwright

# Optional Anthropic integration
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

INPUT_DIR = Path("input")
OUTPUT_DIR = Path("output")
VIEWPORT = {"width": 1280, "height": 900}
# Extra wait (ms) for complex diagrams to finish rendering
RENDER_WAIT_MS = 2500


# ---------------------------------------------------------------------------
# HTML template – loads mermaid.js from CDN, no Node required
# ---------------------------------------------------------------------------

HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{
      margin: 0;
      padding: 24px;
      background: #ffffff;
      font-family: sans-serif;
      display: flex;
      justify-content: center;
    }}
    .mermaid {{
      max-width: 100%;
    }}
  </style>
</head>
<body>
  <div class="mermaid">
{code}
  </div>
  <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
  <script>
    mermaid.initialize({{
      startOnLoad: true,
      theme: 'default',
      securityLevel: 'loose',
      flowchart: {{ useMaxWidth: true }},
      sequence:   {{ useMaxWidth: true }},
    }});
  </script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def extract_mermaid_blocks(md_text: str) -> list[str]:
    """Return a list of mermaid code strings found in a markdown document."""
    pattern = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
    return [m.group(1).strip() for m in pattern.finditer(md_text)]


def safe_stem(text: str, max_len: int = 40) -> str:
    """Turn the first line of mermaid code into a safe filename fragment."""
    first_line = text.strip().splitlines()[0]
    cleaned = re.sub(r"[^a-zA-Z0-9_\-]", "_", first_line)
    return cleaned[:max_len].strip("_") or "diagram"


def describe_diagram(code: str, api_key: str) -> str:
    """Ask Claude to describe the diagram in plain English."""
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        messages=[
            {
                "role": "user",
                "content": (
                    "Describe the following Mermaid diagram in 2-3 concise sentences "
                    "suitable as an image alt-text or caption.\n\n"
                    f"```mermaid\n{code}\n```"
                ),
            }
        ],
    )
    return message.content[0].text.strip()


# ---------------------------------------------------------------------------
# Core rendering
# ---------------------------------------------------------------------------

def render_diagram(page, code: str, output_path: Path) -> None:
    """Render a single mermaid code block and save a PNG screenshot."""
    html = HTML_TEMPLATE.format(code=textwrap.indent(code, "    "))
    page.set_content(html, wait_until="networkidle")

    # Wait for the SVG to appear inside the mermaid div
    try:
        page.wait_for_selector(".mermaid svg", timeout=15_000)
    except Exception:
        print(f"    [warn] SVG did not appear for: {output_path.name} — saving full page anyway")

    page.wait_for_timeout(RENDER_WAIT_MS)

    svg_locator = page.locator(".mermaid svg")
    if svg_locator.count():
        # Expand viewport to fit the SVG before screenshotting
        bbox = svg_locator.bounding_box()
        if bbox:
            page.set_viewport_size({
                "width": max(VIEWPORT["width"], int(bbox["width"]) + 60),
                "height": max(VIEWPORT["height"], int(bbox["height"]) + 60),
            })
        svg_locator.first.screenshot(path=str(output_path))
    else:
        page.screenshot(path=str(output_path), full_page=True)


def process_files(api_key: str | None = None) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)

    md_files = sorted(INPUT_DIR.glob("*.md"))
    if not md_files:
        print(f"No .md files found in {INPUT_DIR}/")
        return

    total_diagrams = 0

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(viewport=VIEWPORT, device_scale_factor=2)
        page = context.new_page()

        for md_file in md_files:
            print(f"\n[file] {md_file.name}")
            text = md_file.read_text(encoding="utf-8")
            blocks = extract_mermaid_blocks(text)

            if not blocks:
                print("  No mermaid blocks found — skipping")
                continue

            for idx, code in enumerate(blocks, start=1):
                stem = safe_stem(code)
                img_name = f"{md_file.stem}_{idx:02d}_{stem}.png"
                img_path = OUTPUT_DIR / img_name

                print(f"  [{idx}/{len(blocks)}] rendering -> {img_name}")
                try:
                    render_diagram(page, code, img_path)
                    total_diagrams += 1
                except Exception as exc:
                    print(f"    [error] {exc}")
                    continue

                # Optional: Claude-generated description
                if api_key and ANTHROPIC_AVAILABLE:
                    try:
                        desc = describe_diagram(code, api_key)
                        txt_path = img_path.with_suffix(".txt")
                        txt_path.write_text(desc, encoding="utf-8")
                        print(f"    description saved -> {txt_path.name}")
                    except Exception as exc:
                        print(f"    [warn] Claude description failed: {exc}")

        context.close()
        browser.close()

    print(f"\nDone — {total_diagrams} diagram(s) saved to {OUTPUT_DIR}/")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if api_key and ANTHROPIC_AVAILABLE:
        print("Anthropic API key found — diagram descriptions will be generated.")
    elif api_key and not ANTHROPIC_AVAILABLE:
        print("ANTHROPIC_API_KEY set but 'anthropic' package not installed — skipping descriptions.")
    else:
        print("No ANTHROPIC_API_KEY — skipping diagram descriptions.")

    process_files(api_key=api_key)
