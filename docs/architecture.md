# System Architecture

The GeM Procurement Intelligence Platform is built on a highly decoupled, layered architecture to ensure maintainability, resilience, and scalability. By strictly separating the concerns of automation, extraction, cleaning, and reporting, the platform can easily adapt to upstream UI changes without breaking downstream data pipelines.

## Layered Architecture Diagram

```mermaid
graph TD
    subgraph Automation Layer
        A[DriverFactory] --> B(GemPortalScraper)
        B --> C{StateManager}
        B --> D[BrowserManager]
    end

    subgraph Extraction Layer
        E[ListingExtractor]
        F[BidDetailExtractor]
        G[VendorEvaluationExtractor]
        B -.-> E
        B -.-> F
        B -.-> G
    end

    subgraph Normalization Layer
        H[DataNormalizer]
        H -.-> I(Clean Datetime)
        H -.-> J(Clean Currency/Numeric)
        H -.-> K(Clean Text/Unicode)
    end

    subgraph Intelligence Layer
        L[ProcurementReportGenerator]
        L -.-> M(Vendor Intelligence)
        L -.-> N(Pricing Spread Analytics)
        L -.-> O(Anomaly Detection)
    end

    subgraph Data Flow
        E & F & G -->|Raw Data| P[(data/raw/)]
        P --> H
        H -->|Clean Data| Q[(data/cleaned/)]
        Q --> L
        L -->|Reports & Dashboards| R[(outputs/)]
    end
    
    style A fill:#2d3748,stroke:#4a5568,color:#fff
    style B fill:#2d3748,stroke:#4a5568,color:#fff
    style E fill:#2b6cb0,stroke:#2c5282,color:#fff
    style F fill:#2b6cb0,stroke:#2c5282,color:#fff
    style G fill:#2b6cb0,stroke:#2c5282,color:#fff
    style H fill:#38a169,stroke:#276749,color:#fff
    style L fill:#d69e2e,stroke:#975a16,color:#fff
```

## Core Components

### 1. Automation Layer (`scraper`)
Orchestrates the Selenium WebDriver. It handles explicit waits, dynamic DOM synchronization, retries, multi-tab navigation, and state checkpointing.
- **Resilience**: Uses `robust_click` and `find_element_with_fallback` to survive minor UI changes.
- **State Checkpointing**: Saves progress to `data/raw/scraper_state.json` after every page to enable crash recovery.

### 2. Extraction Layer (`extractor`)
Parses HTML elements into structured dictionaries.
- **Dynamic Mapping**: The `VendorEvaluationExtractor` uses synonym dictionaries (`_TECH_COL_SYNONYMS`, `_FIN_COL_SYNONYMS`) to map column headers dynamically instead of relying on hardcoded indexes.

### 3. Normalization Layer (`cleaner`)
The `DataNormalizer` standardizes the raw extracted data.
- **ISO 8601**: Converts varying date strings into strict ISO formats.
- **Schema Stability**: Ensures all output DataFrames have a fixed column schema, filling missing fields with `None` to prevent downstream SQL ingestion errors.

### 4. Intelligence Layer (`insights`)
The `ProcurementReportGenerator` analyzes the cleaned data to produce business value.
- **Anomaly Detection**: Identifies single-vendor bids, duplicated pricing, and abnormal spreads.
- **Dashboards**: Generates a static HTML dashboard and BI-ready CSVs.
