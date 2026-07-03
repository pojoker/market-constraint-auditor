#!/usr/bin/env python3
"""Convert a Markdown report to HTML and PDF.

Usage:
    python3 convert_md.py <path/to/report.md> [more.md ...]

Generates <report>.html and <report>.pdf alongside each input file.

PDF is rendered with headless Google Chrome / Chromium (`--print-to-pdf`),
producing the same A4 / PingFang-styled output used for every market-constraint
report since 2026-04 (PDF Producer: "Skia/PDF"). Requires the `markdown`
package and a Chrome/Chromium install. Do NOT swap in markdown_pdf / PyMuPDF or
gstack make-pdf — they produce a different layout that breaks visual continuity
with prior reports.
"""

import os
import subprocess
import sys
from pathlib import Path

import markdown

# HTML template with print-oriented styling (A4, CJK fonts). Kept byte-for-byte
# in sync with the long-standing md-to-pdf template so output stays identical.
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        @page {{
            margin: 2cm 1.5cm;
            size: A4;
        }}

        * {{
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "PingFang SC", "Microsoft YaHei", sans-serif;
            font-size: 11pt;
            line-height: 1.7;
            color: #333;
            max-width: 100%;
            margin: 0;
            padding: 0;
        }}

        h1 {{
            font-size: 20pt;
            color: #1a365d;
            border-bottom: 3px solid #3182ce;
            padding-bottom: 12px;
            margin-top: 0;
            margin-bottom: 20px;
        }}

        h2 {{
            font-size: 14pt;
            color: #2d3748;
            margin-top: 28px;
            margin-bottom: 14px;
            border-left: 4px solid #3182ce;
            padding-left: 12px;
        }}

        h3 {{
            font-size: 12pt;
            color: #4a5568;
            margin-top: 20px;
            margin-bottom: 10px;
        }}

        p {{
            margin: 10px 0;
            text-align: justify;
        }}

        /* Beautiful table styling */
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 16px 0;
            font-size: 9.5pt;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}

        th {{
            background: linear-gradient(135deg, #3182ce 0%, #2c5282 100%);
            color: white;
            font-weight: 600;
            padding: 10px 8px;
            text-align: left;
            border: 1px solid #2c5282;
        }}

        td {{
            padding: 8px;
            border: 1px solid #e2e8f0;
            vertical-align: top;
        }}

        tr:nth-child(even) {{
            background-color: #f7fafc;
        }}

        tr:hover {{
            background-color: #edf2f7;
        }}

        /* Code styling */
        code {{
            background: #edf2f7;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: "SF Mono", Monaco, Consolas, monospace;
            font-size: 10pt;
            color: #744210;
        }}

        pre {{
            background: #2d3748;
            color: #e2e8f0;
            padding: 16px;
            border-radius: 8px;
            overflow-x: auto;
            font-size: 9.5pt;
            line-height: 1.5;
        }}

        pre code {{
            background: transparent;
            color: inherit;
            padding: 0;
        }}

        /* Blockquote */
        blockquote {{
            border-left: 4px solid #3182ce;
            margin: 16px 0;
            padding: 12px 20px;
            background: #ebf8ff;
            color: #2c5282;
            font-style: italic;
            border-radius: 0 8px 8px 0;
        }}

        /* Links */
        a {{
            color: #3182ce;
            text-decoration: none;
        }}

        a:hover {{
            text-decoration: underline;
        }}

        /* Horizontal rule */
        hr {{
            border: none;
            height: 2px;
            background: linear-gradient(90deg, transparent, #cbd5e0, transparent);
            margin: 30px 0;
        }}

        /* Lists */
        ul, ol {{
            padding-left: 28px;
            margin: 12px 0;
        }}

        li {{
            margin: 6px 0;
        }}

        /* Strong emphasis */
        strong {{
            color: #1a202c;
            font-weight: 600;
        }}

        /* Emphasis */
        em {{
            color: #4a5568;
        }}
    </style>
</head>
<body>
{content}
</body>
</html>"""

CHROME_PATHS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
]


def convert_md_to_html(md_path):
    """Convert Markdown file to styled HTML."""
    md_path = Path(md_path)

    with open(md_path, 'r', encoding='utf-8') as f:
        md_content = f.read()

    html_content = markdown.markdown(
        md_content,
        extensions=['tables', 'fenced_code', 'toc']
    )

    full_html = HTML_TEMPLATE.format(title=md_path.stem, content=html_content)

    html_path = md_path.with_suffix('.html')
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(full_html)

    print(f"✅ HTML generated: {html_path}")
    return html_path


def find_chrome():
    """Locate a Chrome/Chromium binary, or return None."""
    for path in CHROME_PATHS:
        if os.path.exists(path):
            return path
    return None


def convert_html_to_pdf(html_path, pdf_path=None):
    """Convert HTML to PDF using headless Chrome (Skia/PDF output)."""
    html_path = Path(html_path)
    if pdf_path is None:
        pdf_path = html_path.with_suffix('.pdf')

    chrome_path = find_chrome()
    if chrome_path is None:
        raise RuntimeError(
            "Chrome/Chromium not found. Install Google Chrome to render PDFs.\n"
            "macOS: https://www.google.com/chrome/\n"
            "Linux: sudo apt install google-chrome-stable"
        )

    cmd = [
        chrome_path,
        "--headless",
        "--disable-gpu",
        "--print-to-pdf-no-header",
        f"--print-to-pdf={pdf_path}",
        str(html_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Chrome error: {result.stderr}", file=sys.stderr)
        raise RuntimeError("PDF conversion failed")

    print(f"✅ PDF generated: {pdf_path}")
    return pdf_path


def main():
    args = sys.argv[1:]
    if not args:
        print("Usage: python3 convert_md.py <path/to/report.md> [more.md ...]",
              file=sys.stderr)
        sys.exit(1)

    exit_code = 0
    for md_file in args:
        md_path = Path(md_file)
        if not md_path.is_file():
            print(f"❌ Not found: {md_file}", file=sys.stderr)
            exit_code = 1
            continue
        print(f"📄 Converting: {md_file}")
        print("-" * 40)
        try:
            html_path = convert_md_to_html(md_path)
            convert_html_to_pdf(html_path)
        except Exception as e:  # noqa: BLE001 - report and continue
            print(f"❌ Error: {e}", file=sys.stderr)
            exit_code = 1
        print("-" * 40)

    print("🎉 Conversion completed!")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
