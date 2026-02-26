# Design Document - Facebook Marketplace RSS Monitor

## System Architecture

The Facebook Marketplace RSS Monitor is a self-contained Rust application that combines high-performance web scraping, persistent data storage, and an asynchronous web server.

### Components

1.  **Main Orchestration (`main.rs`)**: Uses the Tokio multi-threaded runtime to manage the lifecycle of the web server and the background monitoring loop.
    *   **Background Loop**: A non-blocking Tokio task that triggers ad checks, handles scraper initialization/cleanup, and manages jittered delays.
    *   **Selenium Integration (`scraper.rs`)**: Uses `thirtyfour` for browser automation and the `scraper` crate for efficient HTML parsing via CSS selectors.
    *   **Filter Engine (`filter.rs`)**: Implements a robust multi-level keyword filtering system (AND between levels, OR within levels).
2.  **Data Layer (`db.rs`)**:
    *   **Pooled SQLite**: Managed by `r2d2` and `r2d2_sqlite` to provide thread-safe, concurrent access from both the background loop and web handlers.
3.  **Web Layer (`web.rs`)**:
    *   **Axum Web Framework**: Serves the RSS feed, health status, and a modern configuration UI.
    *   **RSS Generator (`rss_gen.rs`)**: Uses the `rss` crate to produce spec-compliant XML.
    *   **Static Asset Serving**: Uses `tower-http` to serve the configuration UI's HTML and CSS.

## Data Flow

1.  **Trigger**: The background Tokio loop wakes up.
2.  **Re-init**: The `Scraper` instance is initialized (browser started).
3.  **Fetch**: Selenium loads user-configured Marketplace URLs.
4.  **Extract**: The `scraper` crate extracts ad metadata (hash, title, price, URL).
5.  **Filter**: Ads are checked against keywords; only relevant ones proceed.
6.  **Persist**: The database confirms if ads are new or updated.
7.  **Serve**: Clients request `/rss` or `/edit`, and Axum responds using the shared application state and database pool.

## Technology Stack

*   **Language**: Rust (edition 2024, requires 1.85+)
*   **Async Runtime**: Tokio
*   **Web Framework**: Axum
*   **Scraping**: Selenium (`thirtyfour`), `scraper`
*   **Database**: SQLite (`rusqlite`, `r2d2`)
*   **RSS Generation**: `rss` crate
*   **Logging**: `tracing`, `tracing-subscriber`
*   **Deployment**: Docker (Multi-stage build)
