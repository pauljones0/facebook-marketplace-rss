# Facebook Marketplace RSS Monitor

## Overview

Facebook Marketplace RSS Monitor is a Rust application designed to scrape Facebook Marketplace search results, filter ads based on user-defined keywords, and generate an RSS feed for new listings. This allows users to stay updated on items of interest without manually checking the Marketplace.

The application uses Selenium (`thirtyfour`) with Firefox to browse and extract ad data, Axum to serve the RSS feed and a web-based configuration editor, Tokio for asynchronous scheduling and concurrency, and SQLite (`rusqlite`) to store information about seen ads and prevent duplicates.

## Key Features

*   **Automated Ad Monitoring:** Regularly scrapes specified Facebook Marketplace search URLs.
*   **Multi-Level Keyword Filtering:** Filters ads based on their titles using a flexible, multi-level keyword system:
    *   Keywords within the same level are treated with OR logic.
    *   Keywords across different levels are treated with AND logic.
*   **RSS Feed Generation:** Provides an RSS feed (`/rss`) of new and relevant ads, compatible with standard RSS readers.
*   **Web-Based Configuration:** Offers an intuitive web interface (`/edit`) to manage all application settings, including URLs to monitor and keyword filters. Changes are applied dynamically where possible.
*   **Persistent Ad Storage:** Uses an SQLite database to keep track of ads, ensuring users are notified only of new listings.
*   **Old Ad Pruning:** Automatically removes old ad entries from the database (default: ads not seen for 14 days).
*   **Configurable:** Settings like server IP/port, currency, refresh interval, log file, and database name can be customized.
*   **Docker Support:** Includes a [`Dockerfile`](Dockerfile:1) and [`docker-compose.yml`](docker-compose.yml:1) for easy containerized deployment.
*   **Logging:** Comprehensive logging using `tracing` with configurable levels and output.

## Prerequisites

### Software & Tools
*   **Rust Toolchain:** (e.g., Stable 1.81+).
*   **Cargo:** Rust's package manager and build tool.
*   **Firefox Browser:** Required by Selenium for web scraping.
*   **GeckoDriver:** WebDriver for Firefox.
*   **Docker & Docker Compose:** (Optional, for containerized deployment).

### Rust Crates
The application relies on several high-quality Rust crates:
*   `axum` - Web server framework
*   `tokio` - Asynchronous runtime
*   `thirtyfour` - Selenium WebDriver client
*   `rusqlite` - SQLite wrapper
*   `rss` - RSS feed generation
*   `scraper` - HTML parsing
*   `serde` - Serialization/Deserialization
*   `tracing` - Logging and instrumentation

## Installation

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/bethekind/facebook-marketplace-rss.git
    cd facebook-marketplace-rss
    ```

### Manual Setup

1.  **Install Rust:** Follow instructions at [rust-lang.org](https://www.rust-lang.org/tools/install).
2.  **Install Firefox and GeckoDriver:** Ensure both are in your system's PATH.
3.  **Build the Project:**
    ```bash
    cargo build --release
    ```

### Docker Setup

This is the recommended method for deployment.

#### Building the Docker Image Locally
To build the Docker image yourself:
```bash
docker build -t bethekind/fb-mp-rss:latest .
```

#### Running with Docker Compose (Recommended)
This method uses the [`docker-compose.yml`](docker-compose.yml:1) file.
1.  Ensure Docker and Docker Compose are installed.
2.  Create a `config.json` file in the project root directory (you can copy and modify [`config.sample.json`](config.sample.json:1)).
3.  Run the application:
    ```bash
    docker-compose up -d
    ```
    The application will be accessible at `http://localhost:5000` (or your configured port).

## Configuration

Configuration is primarily managed through a `config.json` file located in the project's root directory (or as specified by the `CONFIG_FILE` environment variable).

### `config.json` File Overview

Create `config.json` by copying and modifying [`config.sample.json`](config.sample.json:1).

```json
{
    "server_ip": "0.0.0.0",
    "server_port": 5000,
    "currency": "$",
    "refresh_interval_minutes": 15,
    "log_filename": "fb-rssfeed.log",
    "database_name": "fb-rss-feed.db",
    "url_filters": {
        "https://www.facebook.com/marketplace/category/search?query=smart%20tv&exact=false": {
            "level1": ["tv"],
            "level2": ["smart"],
            "level3": ["55\"", "55 inch"]
        },
        "https://www.facebook.com/marketplace/category/search?query=free%20stuff&exact=false": {}
    }
}
```

### Configuration Parameters

*   `server_ip` (String): The IP address the web server will listen on. Default: `"0.0.0.0"`.
*   `server_port` (Integer): The port the web server will run on. Default: `5000`.
*   `currency` (String): The currency symbol (e.g., "$", "€"). Default: `"$"`
*   `refresh_interval_minutes` (Integer): How often (in minutes) to check for new ads. Default: `15`.
*   `log_filename` (String): The name of the log file. Default: `"fb_monitor.log"`.
*   `database_name` (String): The name of the SQLite database file. Default: `"fb-rss-feed.db"`.
*   `url_filters` (Object): A dictionary where each key is a Facebook Marketplace search URL and values are keyword level filters.

### Environment Variables

*   `CONFIG_FILE`: Specifies the path to the `config.json` file.
*   `RUST_LOG`: Sets the logging verbosity (e.g., `info`, `debug`). Default is `info`.

## Running the Application

### With Docker Compose (Recommended)

1.  Ensure `config.json` is present in the project root.
2.  Start the services:
    ```bash
    docker-compose up -d
    ```

### Manually

1.  Ensure all prerequisites are met.
2.  Run the application:
    ```bash
    cargo run --release
    ```

## Usage

Once the application is running:

*   **RSS Feed:** Access the generated RSS feed at:
    `http://<server_ip>:<server_port>/rss`
    (e.g., `http://localhost:5000/rss`)
    Add this URL to your preferred RSS feed reader (e.g., Feedbro, Feedly, Thunderbird). The feed includes ads found/checked recently (typically within the last 7 days).

*   **Configuration Editor:** Manage application settings via the web UI at:
    `http://<server_ip>:<server_port>/edit`
    (e.g., `http://localhost:5000/edit`)

## Pushing the Image to Docker Hub (for Maintainer `bethekind`)

1.  **Log in to Docker Hub:**
    ```bash
    docker login
    ```
    Enter your Docker Hub username (`bethekind`) and password when prompted.

2.  **Build and Tag the Image (if not already done):**
    Ensure your locally built image is tagged correctly. If you built it with a different tag or just have an image ID, retag it:
    ```bash
    # If you built it as 'fb-mp-rss:latest' locally, or you have the image ID:
    # docker tag fb-mp-rss:latest bethekind/fb-mp-rss:latest
    # OR
    # docker tag <image-id> bethekind/fb-mp-rss:latest

    # If you already built it with 'docker build -t bethekind/fb-mp-rss:latest .', this step is done.
    docker build -t bethekind/fb-mp-rss:latest .
    ```

3.  **Push the Image:**
    ```bash
    docker push bethekind/fb-mp-rss:latest
    ```

## Logging

*   Logs are written to the file specified by `log_filename` in `config.json` (e.g., `fb-rssfeed.log`).
*   The log level can be set using the `LOG_LEVEL` environment variable (e.g., `INFO`, `DEBUG`). Default is `INFO`.
*   Logs are rotated, with a maximum size of 10MB and 2 backup files.

## Database

*   The application uses an SQLite database (filename configured via `database_name` in `config.json`, e.g., `fb-rss-feed.db`) to store details of ads it has processed.
*   The database schema for the `ad_changes` table is:
    *   `id` (INTEGER, Primary Key, Auto-increment)
    *   `url` (TEXT, Ad's specific URL)
    *   `ad_id` (TEXT, Unique hash of the ad URL)
    *   `title` (TEXT, Ad title)
    *   `price` (TEXT, Ad price)
    *   `first_seen` (TEXT, ISO datetime string in UTC when the ad was first detected)
    *   `last_checked` (TEXT, ISO datetime string in UTC when the ad was last checked/seen)
*   Indexes are created on `ad_id` and `last_checked` for performance.
*   The database is initialized automatically if it doesn't exist when the application starts.
*   Old ads (default: not seen in 14 days) are pruned from the database during each ad check cycle.

## How It Works

1.  **Configuration Loading:** Reads settings from `config.json` using `serde_json`.
2.  **Scheduler:** A Tokio-spawned background loop runs periodic ad checks based on `refresh_interval_minutes`.
3.  **Scraping:**
    *   For each monitored URL, Selenium (`thirtyfour` with Firefox) navigates to the page.
    *   The `scraper` crate parses the HTML content.
    *   Ad details (title, price, link) are extracted using CSS selectors.
4.  **Filtering:** Extracted ad titles are checked against multi-level keyword filters in `filter.rs`.
5.  **Database Interaction:**
    *   Ads are stored in an SQLite database using `rusqlite` with `r2d2` connection pooling.
    *   The `last_checked`, `title`, and `price` fields are updated for existing ads.
6.  **RSS Feed Generation:** The `/rss` endpoint queries the database for recent ads and generates an RSS XML feed using the `rss` crate.
7.  **Web Server:** Axum serves the RSS feed and the `/edit` configuration UI. tokio handles the asynchronous execution.

## License

This project is licensed under the BSD 3-Clause License.
Copyright for the original portions of the project belongs to 'regek' (2024).
Copyright for subsequent contributions belongs to 'bethekind' (2025).

Please see the [`LICENSE`](LICENSE:0) file in the root directory of this source tree for the full license text and details on all copyright holders.
If a `NOTICE` file is present, it may contain additional attribution details.
