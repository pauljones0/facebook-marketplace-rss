# Specification Document - Facebook Marketplace RSS Monitor

## Functional Specifications

1.  **Search URL Monitoring**: The system shall monitor multiple Facebook Marketplace search URLs concurrently using a background loop with randomized jittered delays (2-10s) between requests.
2.  **Health Monitoring**: The system shall provide a `/health` endpoint returning the application status, database connectivity, and uptime.
3.  **Multi-Level Keywords**: The system shall support multi-level keyword filtering for each URL.
    *   **Level Logic**: Keywords within a level are OR-ed. Levels are AND-ed.
4.  **RSS Generation**: The system shall provide an RSS 2.0 compliant feed at the `/rss` endpoint using the `rss` crate.
    *   **Feed Items**: Shall include the ad title, price, link, and a unique GUID (MD5 hash of URL).
5.  **Configuration Management**: The system shall provide a web-based UI at `/edit` and a REST API at `/api/config` to:
    *   Add/Remove monitored URLs.
    *   Manage keyword levels and keywords per URL.
    *   Update server settings (IP, Port, Currency, Refresh Interval).
6.  **Dynamic Configuration**: Changes made via the UI shall be persisted to `config.json` and applied dynamically to the running monitor loop.
7.  **Persistence**: The system shall use an SQLite database with `r2d2` connection pooling to track seen ads and avoid duplicates.
8.  **Auto-Pruning**: The system shall automatically remove ad entries from the database that have not been seen for more than 14 days.

## Non-Functional Specifications

1.  **Performance**: The scraping process shall be optimized using `thirtyfour` (Selenium) and the `scraper` crate, reusing browser instances across URL checks within a cycle.
2.  **Reliability**: The system shall handle network errors, Selenium failures, and database lock contention gracefully using Tokio's asynchronous primitives.
3.  **Concurrency**: The background monitor and the Axum web server shall run concurrently using Tokio's multi-threaded runtime.
4.  **Deployability**: The system shall be deployable via Docker using a multi-stage build for minimal image size.
5.  **Logging & Errors**: The system shall use the `tracing` crate for structured logging and return standardized JSON error responses.
