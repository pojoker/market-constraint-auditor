#!/usr/bin/env python3
"""Convert Markdown to HTML and PDF"""

import markdown
from markdown_pdf import MarkdownPdf, Section
import sys
from pathlib import Path

# HTML template with styling
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 900px;
            margin: 0 auto;
            padding: 40px 20px;
            background: #fff;
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #34495e;
            margin-top: 30px;
            border-left: 4px solid #3498db;
            padding-left: 15px;
        }}
        h3 {{
            color: #34495e;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 20px 0;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 12px;
            text-align: left;
        }}
        th {{
            background-color: #3498db;
            color: white;
        }}
        tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        tr:hover {{
            background-color: #f1f1f1;
        }}
        code {{
            background: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: Monaco, Consolas, monospace;
        }}
        pre {{
            background: #f4f4f4;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
        }}
        blockquote {{
            border-left: 4px solid #3498db;
            margin: 0;
            padding-left: 20px;
            color: #555;
            font-style: italic;
        }}
        a {{
            color: #3498db;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        hr {{
            border: none;
            border-top: 1px solid #eee;
            margin: 30px 0;
        }}
        ul, ol {{
            padding-left: 25px;
        }}
        li {{
            margin: 5px 0;
        }}
        strong {{
            color: #2c3e50;
        }}
    </style>
</head>
<body>
{content}
</body>
</html>"""

def convert_md_to_html(md_file):
    """Convert Markdown file to HTML"""
    md_path = Path(md_file)
    
    # Read markdown content
    with open(md_path, 'r', encoding='utf-8') as f:
        md_content = f.read()
    
    # Convert to HTML
    html_content = markdown.markdown(
        md_content,
        extensions=['tables', 'fenced_code', 'toc']
    )
    
    # Extract title from first h1 or use filename
    title = md_path.stem
    
    # Wrap in template
    full_html = HTML_TEMPLATE.format(title=title, content=html_content)
    
    # Write HTML file
    html_path = md_path.with_suffix('.html')
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(full_html)
    
    print(f"✅ HTML generated: {html_path}")
    return html_path

def convert_md_to_pdf(md_file):
    """Convert Markdown file to PDF using markdown-pdf"""
    md_path = Path(md_file)
    pdf_path = md_path.with_suffix('.pdf')
    
    # Read markdown content
    with open(md_path, 'r', encoding='utf-8') as f:
        md_content = f.read()
    
    # Create PDF
    pdf = MarkdownPdf(toc_level=2)
    pdf.add_section(Section(md_content, toc=False))
    pdf.save(str(pdf_path))
    
    print(f"✅ PDF generated: {pdf_path}")
    return pdf_path

def main():
    md_file = "20260406--市场约束诊断-霍尔木兹危机.md"
    
    print(f"📄 Converting: {md_file}")
    print("-" * 40)
    
    # Convert to HTML
    convert_md_to_html(md_file)
    
    # Convert to PDF
    convert_md_to_pdf(md_file)
    
    print("-" * 40)
    print("🎉 Conversion completed!")

if __name__ == "__main__":
    main()
