"""
PDF content extraction — handles all common PDF types:
  - Presentation style (Tesla, investor decks)
  - Simple financial statements (XYZ, basic reports)
  - Complex annual reports (10-K, mixed layouts)
  - Scanned PDFs (with OCR fallback message)
  - Bank statements, invoices, mixed formats
"""
import os
import pdfplumber
from dotenv import load_dotenv
load_dotenv()

try:
    from crewai_tools.tools.serper_dev_tool.serper_dev_tool import SerperDevTool
    search_tool = SerperDevTool()
except Exception:
    search_tool = None


def _is_chart_page(text: str, tables: list) -> bool:
    """
    Detect if a page is primarily a chart/image page with no useful data.
    These pages have many empty table cells but no real financial figures.
    """
    if not tables:
        return False
    for table in tables:
        # Count non-empty cells
        total_cells = sum(len(row) for row in table)
        empty_cells  = sum(
            1 for row in table
            for cell in row
            if not cell or not str(cell).strip()
        )
        # If more than 90% of cells are empty it's a chart page
        if total_cells > 0 and (empty_cells / total_cells) > 0.90:
            return True
    return False


def _extract_table_smart(page) -> list[str]:
    """
    Try multiple table extraction strategies and return the best result.
    Handles both line-bordered tables and borderless text-aligned tables.
    """
    results = []

    # Strategy 1: Use explicit lines (works for tables with visible borders)
    try:
        tables = page.extract_tables({
            "vertical_strategy"  : "lines",
            "horizontal_strategy": "lines",
        })
        if tables:
            for table in tables:
                if _is_meaningful_table(table):
                    results.append(("lines", table))
    except Exception:
        pass

    # Strategy 2: Use text alignment (works for borderless tables like XYZ)
    try:
        tables = page.extract_tables({
            "vertical_strategy"  : "text",
            "horizontal_strategy": "text",
        })
        if tables:
            for table in tables:
                if _is_meaningful_table(table):
                    results.append(("text", table))
    except Exception:
        pass

    # Strategy 3: Default pdfplumber strategy (fallback)
    try:
        tables = page.extract_tables()
        if tables:
            for table in tables:
                if _is_meaningful_table(table):
                    results.append(("default", table))
    except Exception:
        pass

    # Deduplicate — prefer lines strategy, then text, then default
    seen   = set()
    unique = []
    for strategy, table in results:
        # Use first row as fingerprint to detect duplicates
        key = str(table[0]) if table else ""
        if key not in seen:
            seen.add(key)
            unique.append((strategy, table))

    return unique


def _is_meaningful_table(table: list) -> bool:
    """
    Check if a table has actual financial content worth including.
    Filters out chart-backing tables that are all empty cells.
    """
    if not table:
        return False

    # Count non-empty cells
    total = sum(len(row) for row in table)
    if total == 0:
        return False

    non_empty = sum(
        1 for row in table
        for cell in row
        if cell and str(cell).strip()
    )

    # Table must have at least 20% non-empty cells to be meaningful
    return (non_empty / total) >= 0.20


def _format_table(table: list, strategy: str) -> str:
    """
    Format a table as pipe-separated rows with column headers preserved.
    Adds year/period context from header row.
    """
    output = ""

    # Find header row (first non-empty row)
    header_row = None
    for row in table:
        if any(cell and str(cell).strip() for cell in row):
            header_row = row
            break

    for row_idx, row in enumerate(table):
        # Skip completely empty rows
        if not any(cell and str(cell).strip() for cell in row):
            continue

        cleaned = []
        for cell in row:
            val = str(cell).strip() if cell else ""
            # Normalize newlines within cells
            val = val.replace("\n", " ").strip()
            cleaned.append(val)

        output += " | ".join(cleaned) + "\n"

    return output


def read_pdf_content(file_path: str) -> str:
    """
    Read a PDF file and return its full text + table content.
    Handles all common PDF types intelligently.

    Called directly in Python (crew_runner.py) — NOT passed through LLM.
    """
    if not file_path or not file_path.strip():
        return "Error: No file path provided."

    # Normalize path — handles Windows backslashes
    path = os.path.normpath(file_path.strip())

    if not os.path.exists(path):
        path_fwd = file_path.strip().replace("\\", "/")
        if os.path.exists(path_fwd):
            path = path_fwd
        else:
            data_dir = os.path.dirname(path)
            files    = os.listdir(data_dir) if os.path.exists(data_dir) else []
            return (
                f"Error: File not found at '{path}'.\n"
                f"Files in folder: {files}"
            )

    try:
        full_report  = ""
        pages_with_data = 0

        with pdfplumber.open(path) as pdf:
            total_pages  = len(pdf.pages)
            full_report += (
                f"[Document: {os.path.basename(path)} | "
                f"Pages: {total_pages}]\n\n"
            )

            for page_num, page in enumerate(pdf.pages, start=1):

                # ── Extract plain text ─────────────────────────────────────
                text = page.extract_text()

                # ── Extract tables smartly ────────────────────────────────
                tables_raw = page.extract_tables()
                is_chart   = _is_chart_page(text or "", tables_raw or [])

                # Skip pages that are pure images/photos with no text
                if not text and not tables_raw:
                    continue

                # Skip chart-only pages (bar charts, line graphs etc.)
                # that have no real tabular data
                if is_chart and (not text or len(text.strip()) < 50):
                    continue

                page_content = f"\n--- Page {page_num} ---\n"

                # Add text content
                if text and text.strip():
                    page_content += text.strip() + "\n"

                # Add meaningful tables only (skip empty chart tables)
                if not is_chart:
                    smart_tables = _extract_table_smart(page)
                    for table_idx, (strategy, table) in enumerate(
                        smart_tables, start=1
                    ):
                        formatted = _format_table(table, strategy)
                        if formatted.strip():
                            page_content += (
                                f"\n[Table {table_idx} on Page {page_num}]\n"
                                f"{formatted}\n"
                            )

                full_report    += page_content
                pages_with_data += 1

        if pages_with_data == 0:
            return (
                f"Warning: PDF opened but no text content found in '{path}'.\n"
                "The PDF may be entirely image-based (scanned). "
                "Please provide a text-based PDF for analysis."
            )

        return full_report.strip()

    except Exception as e:
        return f"Error reading PDF '{path}': {str(e)}"