# Requirements Document - Facebook Marketplace RSS Monitor

## User Requirements

1.  **Automated Monitoring**: I want to automatically monitor Facebook Marketplace for specific items without checking manually.
2.  **Precise Filtering**: I want to filter results using complex keyword logic (e.g., must contain "TV" AND "Smart" AND ("4K" OR "UHD")).
3.  **Real-Time Updates**: I want to be notified of new listings as soon as possible via an RSS reader.
4.  **Premium Configuration Experience**: I want a modern, responsive, and intuitive web interface to manage my search URLs and filters, with real-time feedback on input validity.
5.  **Containerized Deployment**: I want to run the application easily on my server using Docker.

## System Requirements

1.  **Python Environment**: Python 3.10 or higher.
2.  **Browser**: Firefox (and GeckoDriver) must be installed for Selenium scraping.
3.  **Memory**: Sufficient memory for running a headless Firefox instance (approx. 512MB-1GB recommended).
4.  **Network**: Stable internet connection with access to Facebook.com.
5.  **Storage**: Minimal storage for SQLite database and log files (typically <100MB).

## Dependencies

*   `Flask`: Web server framework.
*   `selenium`: Web automation for scraping.
*   `beautifulsoup4`: HTML parsing.
*   `APScheduler`: Task scheduling.
*   `PyRSS2Gen`: RSS feed construction.
*   `waitress`: Production WSGI server.
*   `webdriver-manager`: Automated driver management.
*   `sqlite3`: Included in Python standard library.
