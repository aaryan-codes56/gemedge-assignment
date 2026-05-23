# GeM Procurement Intelligence Scraper Foundation

A production-grade, highly scalable, and modular automation foundation built in Python 3.11+ using Selenium, Pandas, and webdriver-manager.

This project implements the foundational architecture for an advanced procurement intelligence collection system targeting the Government e-Marketplace (GeM) Bids Portal:
[https://bidplus.gem.gov.in/all-bids](https://bidplus.gem.gov.in/all-bids).

---

## 🏛️ Architectural Overview

The project is structured according to the **SOLID Design Principles** and strict separation of concerns to avoid monolithic scripts. Each phase of the data scraping lifecycle is mapped to decoupled, abstract interfaces, making the repository future-proof and resilient to portal changes.

### Core Architecture Layers

1. **Config-Driven Settings (`src.config`)**: Standardized environment variable ingestion, strict timeout policies, and relative path mappings.
2. **Browser Engine (`src.core.driver_factory`)**: Manages isolated Chrome instances with optimal headless sandboxing and anti-detection configurations.
3. **Wait & Retry Engine (`src.core.wait_utils` & `src.core.retry_utils`)**: Reusable decorator-driven retries (exponential backoff) and explicit DOM state monitors instead of random thread sleeps.
4. **Abstract Contracts (`src.scraper`, `src.extractor`, `src.cleaner`, `src.insights`)**: Explicit abstract interface classes establishing modular blueprints for data processing.

---

## 📂 Project Structure

```text
gemedge-procurement-intelligence-scraper/
│
├── data/
│   ├── raw/                  # Downloaded raw JSON page collections
│   └── processed/            # Normalized, schema-enforced tabular outputs
│
├── outputs/                  # High-level analytics reports
│
├── screenshots/              # Error diagnostics screenshots
│
├── logs/                     # Rotation-safe execution logs
│
├── src/
│   ├── __init__.py
│   │
│   ├── config/               # Settings management and absolute path overrides
│   │   ├── __init__.py
│   │   └── settings.py
│   │
│   ├── core/                 # Browser drivers, retry decorators, and DOM wait helpers
│   │   ├── __init__.py
│   │   ├── driver_factory.py
│   │   ├── wait_utils.py
│   │   └── retry_utils.py
│   │
│   ├── utils/                # File handlers and Singleton loggers
│   │   ├── __init__.py
│   │   ├── logger.py
│   │   └── file_utils.py
│   │
│   ├── scraper/              # Interface definitions for Web Scrapers
│   │   └── __init__.py
│   │
│   ├── extractor/            # Interface definitions for Data Extractors
│   │   └── __init__.py
│   │
│   ├── cleaner/              # Interface definitions for Data Cleaners
│   │   └── __init__.py
│   │
│   └── insights/             # Interface definitions for Business Intelligence
│       └── __init__.py
│
├── tests/                    # Core Unit and Integration tests
│
├── .gitignore                # Production cache and ignore configurations
├── requirements.txt          # Python packages
├── README.md                 # Documentation
├── main.py                   # System bootstrap orchestrator
└── journal.md                # Development & engineering log
```

---

## 🛠️ Engineering Principles & Standards

- **Strict Explicit Waits Only**: Random time delays (`time.sleep`) are prohibited. Wait utilities use standard polling to wait for exact conditions.
- **Fail-Safe Operation**: Driver processes are strictly closed via safe shutdown hooks inside `finally` blocks, preventing resource leaks.
- **Retry-Resilient Logic**: Critical network or DOM retrieval methods are decorated with an exponential backoff retry mechanism.
- **Logging-First Mentality**: Console and Rotating File Loggers record tracing information detailing exceptions and warnings.

---

## 🚀 Setup & Installation

### 1. Prerequisite Checklist
- **Python**: Version `3.11` or higher.
- **Google Chrome**: A local installation of Google Chrome or Chromium (ChromeDriver will be downloaded and paired automatically by the driver factory).

### 2. Setup Steps

Clone the repository and navigate to the project directory:
```bash
cd gemedge-procurement-intelligence-scraper
```

Configure a Python virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
```

Install the dependencies:
```bash
pip install -r requirements.txt
```

---

## 🏃 Running the Application

To execute the system bootstrap dry-run and verify the browser is configured correctly:

```bash
python main.py
```

### Expected Output
The system automatically creates the `data/`, `logs/`, `screenshots/`, and `outputs/` directories, fires up the Selenium engine, fetches the target URL, extracts the target site metadata, and cleanly exits:

```text
[2026-05-23 18:55:01] [INFO] [file_utils.py:34] - Verified / Created 5 core system directories.
[2026-05-23 18:55:01] [INFO] [main.py:10] - Initializing gemedge-procurement-intelligence-scraper foundation...
[2026-05-23 18:55:01] [INFO] [main.py:15] - Launching secure automation browser instance...
[2026-05-23 18:55:01] [INFO] [driver_factory.py:20] - Initializing browser in HEADLESS mode.
[2026-05-23 18:55:03] [INFO] [driver_factory.py:53] - Selenium WebDriver created successfully.
[2026-05-23 18:55:03] [INFO] [main.py:19] - Navigating to primary procurement target: https://bidplus.gem.gov.in/all-bids
[2026-05-23 18:55:06] [INFO] [main.py:25] - ==================================================
[2026-05-23 18:55:06] [INFO] [main.py:26] -        SYSTEM FOUNDATION INITIALIZED SUCCESSFULLY   
[2026-05-23 18:55:06] [INFO] [main.py:27] - ==================================================
[2026-05-23 18:55:06] [INFO] [main.py:28] - Verified Title : Bid Plus | Government e-Marketplace (GeM)
[2026-05-23 18:55:06] [INFO] [main.py:29] - Verified URL   : https://bidplus.gem.gov.in/all-bids
[2026-05-23 18:55:06] [INFO] [main.py:30] - ==================================================
[2026-05-23 18:55:06] [INFO] [driver_factory.py:64] - Initiating browser shutdown sequence...
[2026-05-23 18:55:06] [INFO] [driver_factory.py:67] - Browser shut down safely and resources released.
[2026-05-23 18:55:06] [INFO] [main.py:40] - System foundation terminated and cleaned up successfully.
```
