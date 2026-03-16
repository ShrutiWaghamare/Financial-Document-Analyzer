from crewai import Task
from agents import financial_analyst, verifier, investment_advisor, risk_assessor

# ── Step 1: Verify document ────────────────────────────────────────────────────
verification = Task(
    description=(
        "Below is the full extracted content of a financial document.\n"
        "Your job is to verify whether it is a valid financial document "
        "(e.g. earnings report, financial statement, investor update, annual report).\n\n"
        "Check the content for: financial figures, tables, fiscal periods, "
        "GAAP/IFRS terms, revenue/expense data.\n\n"
        "DOCUMENT CONTENT:\n{document_content}\n\n"
        "Respond with a clear YES or NO and 1-2 sentences of justification "
        "based strictly on the content above."
    ),
    expected_output=(
        "YES or NO — whether this is a valid financial document, "
        "with 1-2 sentences of justification based on the document content."
    ),
    agent=verifier,
    async_execution=False,
)

# ── Step 2: Core financial analysis ───────────────────────────────────────────
analyze_financial_document = Task(
    description=(
        "Below is the full extracted content of a financial document.\n"
        "Analyze it to address: {query}\n\n"
        "DOCUMENT CONTENT:\n{document_content}\n\n"

        "CRITICAL RULES FOR READING TABLES:\n"
        "1. Always read column HEADERS first to identify which column = which year/period\n"
        "2. The leftmost data column is usually the MOST RECENT period\n"
        "3. Never assume column order — always verify from headers in the table\n"
        "4. If a table has no headers, use surrounding text to identify periods\n"
        "5. Cross-check figures across multiple tables to confirm accuracy\n\n"

        "YOU MUST cite specific numbers from the content above:\n"
        "- Exact revenue figures with period (e.g. Q2 2025: $22.5B, down 12% YoY)\n"
        "- Gross profit, operating income, net income with exact amounts\n"
        "- Margins: gross %, operating %, net %\n"
        "- EPS: GAAP diluted and non-GAAP diluted (if available)\n"
        "- Operating cash flow, capex, free cash flow\n"
        "- Cash and investments balance\n"
        "- Key balance sheet items\n"
        "- Any YoY or QoQ changes with % figures\n\n"

        "Do NOT write vague statements like 'revenue was reported'.\n"
        "Always write the actual number with its correct period label.\n"
        "Do NOT use any knowledge outside the document content provided."
    ),
    expected_output=(
        "A structured analysis with ACTUAL figures from the document including:\n"
        "- Revenue, gross profit, operating income with exact amounts and % changes\n"
        "- Net income (GAAP and non-GAAP if available), EPS\n"
        "- Cash flow from operations, free cash flow, capex\n"
        "- Key balance sheet items (cash, debt, equity)\n"
        "- Risks and opportunities tied to specific numbers\n"
        "- All figures cited with their correct period label"
    ),
    agent=financial_analyst,
    context=[verification],
    async_execution=False,
)

# ── Step 3: Investment advice ──────────────────────────────────────────────────
investment_analysis = Task(
    description=(
        "Below is the full extracted content of a financial document.\n"
        "Using this data, provide investment insights for: {query}\n\n"
        "DOCUMENT CONTENT:\n{document_content}\n\n"

        "CRITICAL: Always verify column headers before citing figures.\n"
        "Never assume which column is current vs prior year.\n\n"

        "Every recommendation MUST be tied to a specific metric from the content.\n"
        "Example: 'Operating cash flow of $2.5B (Q2 2025) supports...'\n"
        "Include appropriate caveats. Avoid unsupported claims.\n"
        "Do NOT use any knowledge outside the document content provided."
    ),
    expected_output=(
        "Structured investment analysis with:\n"
        "- Specific metrics from the document supporting each recommendation\n"
        "- Exact figures with correct period labels\n"
        "- Clear caveats and data source citations\n"
        "- No claims not supported by the document content"
    ),
    agent=investment_advisor,
    context=[analyze_financial_document],
    async_execution=False,
)

# ── Step 4: Risk assessment ────────────────────────────────────────────────────
risk_assessment = Task(
    description=(
        "Below is the full extracted content of a financial document.\n"
        "Using this data, produce a risk assessment for: {query}\n\n"
        "DOCUMENT CONTENT:\n{document_content}\n\n"

        "CRITICAL: Always verify column headers before citing figures.\n"
        "Never assume which column is current vs prior year.\n\n"

        "Every risk MUST be supported by a specific figure from the content.\n"
        "Example: 'Free cash flow dropped 89% YoY to $0.1B (Q2 2025), indicating...'\n"
        "Use standard risk categories: market, credit, operational, liquidity.\n"
        "Do NOT use any knowledge outside the document content provided."
    ),
    expected_output=(
        "Structured risk assessment with:\n"
        "- Each risk tied to a specific figure from the document\n"
        "- Risk category labels (market, credit, operational, liquidity)\n"
        "- Exact figures with correct period labels as evidence\n"
        "- Realistic mitigations grounded in document data"
    ),
    agent=risk_assessor,
    context=[analyze_financial_document],
    async_execution=False,
)