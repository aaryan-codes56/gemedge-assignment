# GeM Procurement Intelligence Platform

> **Production-grade procurement intelligence scraping and analytics platform built with Python, Selenium, and Pandas. Features resilient automation, deep bid extraction, vendor intelligence analytics, anomaly detection, normalization pipelines, and executive reporting for government procurement data.**

---

## 🎯 Project Overview

The **GeM Procurement Intelligence Platform** is a highly resilient Python-based automation engine designed to monitor, harvest, and analyze public procurement data from the Government e-Marketplace (GeM) portal. It extracts active bid listings, traverses deep detail tabs, captures vendor competition intelligence, normalizes complex procurement datasets, and generates BI-ready analytics reports.

Built with **SOLID principles**, modular architecture, and robust anti-detection mechanisms, this platform is designed to operate autonomously while surviving network fluctuations, DOM mutations, and browser instability.

---

## 💡 The Business Problem

Government procurement portals are notoriously difficult to scrape due to:
1. **Dynamic DOMs**: Elements constantly change IDs and locations.
2. **Anti-Scraping Defenses**: Immediate IP blocking or captcha challenges for naive automation.
3. **Data Fragmentation**: Vital competition data is hidden inside deeply nested, asynchronously loaded accordion panels.
4. **Unstructured Text**: Dates, currencies, and ministry names are inconsistently formatted.

**The Solution:** An intelligent, state-aware automation engine that mimics human interaction, anticipates structural shifts through synonym-based parsing, safely recovers from crashes, and normalizes unstructured data into SQL/BI-ready formats.

---

## 🏗️ System Architecture & Engineering Highlights

This platform uses a heavily decoupled architecture consisting of four independent layers:

1. **Automation Layer (`scraper`)**: Manages the stealth Selenium WebDriver, tab orchestration, DOM synchronization, and health checks.
2. **Extraction Layer (`extractor`)**: Parses raw WebElements/HTML into structured Pydantic-style dataclasses using synonym dictionaries (avoiding brittle hardcoded XPath indexes).
3. **Normalization Layer (`cleaner`)**: Cleanses currencies, standardizes dates to ISO 8601, normalizes unicode text, and resolves dataset integrity.
4. **Intelligence Layer (`insights`)**: Computes competition metrics, vendor win rates, pricing spreads, and flags procurement anomalies.

### Key Engineering Features
- **Stealth & Resilience**: Implements `webdriver-manager` with specialized Chrome options (`--disable-blink-features=AutomationControlled`), custom User-Agents, and intelligent implicit/explicit wait strategies.
- **Stateful Checkpointing**: Persists extraction state to disk after every page, enabling safe resumption from crashes without re-scraping data.
- **Dynamic Header Resolution**: Employs synonym dictionaries (`_TECH_COL_SYNONYMS`) to dynamically map varying table column structures at runtime.
- **Anomaly Detection**: Automatically flags single-vendor bids, suspicious pricing spreads, missing ranks, and duplicate quotes.
- **Multi-Tab Orchestration**: Safely navigates deep result links in background tabs, extracts data, and returns focus without state loss.
- **Singleton Metrics Tracker**: Thread-safe telemetry system (`MetricsTracker` via `RLock`) tracking extraction throughput, anomaly counts, and error rates.

---

## 📂 Folder Structure

```text
gemedge-assignment/
│
├── docs/                # Architecture diagrams and sample outputs
├── outputs/             # BI-ready intelligence reports and HTML dashboard
├── screenshots/         # Dashboard and CLI execution visual evidence
├── src/
│   ├── cleaner/         # DataNormalizer and atomic text/numeric cleaners
│   ├── config/          # Centralized environment and settings configuration
│   ├── core/            # Interfaces (ABCs), Data Models, and DriverFactory
│   ├── extractor/       # Listing, Detail, and Vendor intelligence extractors
│   ├── insights/        # ProcurementReportGenerator and analytics engine
│   ├── scraper/         # Main automation engine and state management
│   └── utils/           # Singletons (Metrics, Logger), retries, and file I/O
├── tests/               # Unit testing suite
├── requirements.txt     # Python dependencies
├── README.md            # Official project documentation
├── main.py              # CLI entry point for the automation scraper
├── run_normalizer.py    # CLI entry point for data cleaning
├── run_reports.py       # CLI entry point for intelligence reporting
└── .env.example         # Environment variables configuration
```

---

## 🚀 How to Run

### Prerequisites
- **Python 3.11 – 3.13** (⚠️ Python 3.14 is not yet supported by Selenium/Pandas)
- Google Chrome installed locally

### Setup
```bash
# Clone the repository
git clone https://github.com/aaryan-codes56/gemedge-assignment.git
cd gemedge-assignment

# Create virtual environment (use python3.13 on macOS)
python3.13 -m venv venv
source venv/bin/activate        # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Execution

**Step 1 — Run the Scraper** (extracts live data from GeM portal)
```bash
python main.py                  # headless mode (recommended)
HEADLESS=false python main.py   # UI mode — watch the browser work
```

**Step 2 — Generate Intelligence Reports** (cleans data → analytics → dashboard)
```bash
python run_reports.py
```

**Step 3 — View Outputs**
Open `outputs/procurement_intelligence_dashboard.html` in any browser to view the analytics dashboard.

> **Note:** `run_reports.py` automatically invokes the cleaning pipeline and generates all CSV, JSON, HTML, and Markdown reports into `outputs/`.

---

## 📊 Analytics & Reporting Outputs

After executing the intelligence pipeline, check the `outputs/` directory for:

1. **`procurement_intelligence_dashboard.html`**: A zero-dependency, static HTML dashboard summarizing all findings.
2. **`executive_summary.md`**: High-level markdown digest of risks, top vendors, and ministry concentration.
3. **`*_intelligence_report.csv`**: Flattened, Tableau/PowerBI-ready CSV datasets detailing vendor performance, pricing spreads, and category analytics.

For detailed sample outputs and architecture diagrams, please refer to the `docs/` folder.
