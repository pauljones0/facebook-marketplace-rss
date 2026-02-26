# Requirements Document - Facebook Marketplace RSS Monitor

## User Requirements

1.  **Automated Monitoring**: I want to automatically monitor Facebook Marketplace for specific items without checking manually.
2.  **Precise Filtering**: I want to filter results using complex keyword logic (e.g., must contain "TV" AND "Smart" AND ("4K" OR "UHD")).
3.  **Real-Time Updates**: I want to be notified of new listings as soon as possible via an RSS reader.
4.  **Premium Configuration Experience**: I want a modern, responsive, and intuitive web interface to manage my search URLs and filters, with real-time feedback on input validity.
5.  **Containerized Deployment**: I want to run the application easily on my server using Docker.

## System Requirements

1.  **Rust Toolchain**: Latest Stable (1.88+).
2.  **Browser**: Firefox must be installed for Selenium scraping.
3.  **GeckoDriver**: The driver for Firefox must be in the PATH or manageable by the app.
4.  **Memory**: Sufficient memory for running a headless Firefox instance (approx. 512MB-1GB recommended).
5.  **Network**: Stable internet connection with access to Facebook.com.
6.  **Storage**: Minimal storage for SQLite database and log files (typically <100MB).

## Dependencies

*   `Axum`: Web server framework.
*   `Tokio`: Asynchronous runtime.
*   `thirtyfour`: Selenium WebDriver client.
*   `scraper`: HTML parsing.
*   `rusqlite`: SQLite database connector.
*   `rss`: RSS feed generation.
*   `tracing`: Structured logging and instrumentation.
*   `serde`: Serialization and deserialization.
