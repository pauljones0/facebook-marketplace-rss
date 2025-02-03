# Facebook Marketplace RSS Feed Generator

## Overview

This project generates an RSS feed for Facebook Marketplace so you can track new ads based on customizable filters. It is built with:

- Selenium for web scraping
- SQLite for ad tracking
- RSS feed generation
- Background job scheduling
- A flexible, configuration-based filtering system

*Tested using Python3 on Linux and Windows 10.*

## Features

- **Configurable Filters:** Define multi-level search keywords per URL.
- **Automated Scheduling:** Checks for new ads at regular intervals.
- **Rate Control:** Auto-adjusts the delay between URL requests based on the number of URLs (with an option for manual override).
- **RSS Feed Generation:** Easily monitor new ads with your favorite RSS reader, such as [Feedly](https://feedly.com/), [Inoreader](https://inoreader.com/), [Tiny Tiny RSS](https://tt-rss.org/), or [FreshRSS](https://freshrss.org/).

## Installation

Follow these steps to get the project running:

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/bethekind/facebook-marketplace-rss.git
   cd facebook-marketplace-rss
   ```

2. **Install Python Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Firefox Browser:**

   - [Linux Installation](https://support.mozilla.org/en-US/kb/install-firefox-linux)
   - [Windows Installation](https://support.mozilla.org/en-US/kb/how-install-firefox-windows)
4. **Configure the Application:**
   - Create your configuration file by copying the example:
     ```bash
     cp config.json.example config.json
     ```
   - Modify `config.json` as needed (e.g., set the `currency`, optionally set `locale` and `request_delay_seconds`, etc).

   - Adjust the settings as needed.  
     
     **Note:**  
     - You must modify at least the `currency` field (e.g., USA: `$`, Canada: `CA$`, Europe: `€`, UK: `£`, Australia: `A$`).
     - The `locale` field is optional. When not specified, the system will use the `base_url` to determine the locale.
     - The `request_delay_seconds` field is optional. If not specified, the system automatically calculates the delay between URL requests based on the number of URLs.
     - **Logging Configuration:** Set the desired log level directly via the `log_level` parameter in your configuration file. Accepted values include `"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"`, and `"CRITICAL"`. If not set, the default log level is `"INFO"`.
     - **Debug Mode:** Use the `"debug"` field to control whether Flask runs in debug mode (with auto-reloading and verbose error messages). This flag is independent of the `log_level`, so you could run with a high log verbosity without enabling Flask's debug mode.
     
   **Example `config.json`:**

   ```json
   {
       "server_ip": "0.0.0.0", // Listen on all IPs or specify an IP address
       "server_port": "5000", // Port for the RSS server
       "currency": "$", // Currency used in your local marketplace
       "refresh_interval_minutes": 15, // Interval for checking new ads (recommened 15 interval minutes)
       "request_delay_seconds": 2, // Optional: Manually set the delay between URL requests
       "log_filename": "fb-rssfeed.log",
       "log_level": "INFO",
       "debug": false,
       "base_url": "https://www.facebook.com/marketplace",

       "locale": "your_locale", // Specify your locale (e.g., "calgary")
       "searches": {
           "example_search_name": {
               "level1": ["keyword1"], // First level of search keywords
               "level2": ["keyword2"] // Second level of search keywords
           }
       }
   }
   ```

## Usage

1. **Initialize the Database:**

   ```bash
   python init_db.py
   ```

5. **Run the Application:**
   ```bash
   python fb_ad_monitor.py
   ```

3. **Access the RSS Feed:**
   
   - **Directly via `/rss`:**  
     Visit `http://server_ip:server_port/rss` to view the RSS feed in XML format.
     
   - **Home Redirection:**  
     Navigating to the base URL (i.e., `http://server_ip:server_port/`) will automatically redirect you to the `/rss` endpoint, providing a convenient entry point.

4. **Logging & Debug Configuration:**

   - **Log Level:**  
     Set the desired log level in your `config.json` via the `log_level` parameter. This controls both Flask's and the application's logging verbosity.
     
   - **Debug Mode:**  
     Control whether Flask runs in debug mode by setting the `"debug"` field in your configuration. This makes development easier when enabled, but it is recommended to set `"debug": false` in production.

## Best Practices for URL Monitoring

The system automatically calculates the delay between URL requests as follows (if no manual override is provided):

| Number of URLs    | Auto-Calculated Delay  | Recommendation                                                                 |
|-------------------|------------------------|--------------------------------------------------------------------------------|
| 1-5 URLs          | 2 seconds              | Ideal for small lists; minimizes job runtime without overwhelming Facebook.  |
| 6-10 URLs         | 2-10 seconds           | Delay is linearly interpolated between 2 and 10 seconds.                       |
| **More than 10**  | **10 seconds**         | 10 seconds is the maximum default delay. If you monitor many URLs, consider setting `request_delay_seconds` manually for a better chance of avoiding throttling or IP bans. |

**Note:**  
- Using a longer delay on large URL lists improves the chance of avoiding throttling or IP bans.
- You can override the auto-calculated delay by specifying the `request_delay_seconds` value in your configuration.

## Docker Container

To run the application in Docker, leave the `server_ip` and `server_port` fields as default, mount your configuration directory, then run:

```bash
docker run --name fb-mp-rss -d \
  -v /path/to/config/directory:/app/config \
  -e CONFIG_FILE=/app/config/config.json \
  -p 5000:5000 \
  bethekind/fb-mp-rss:latest
```

## CI/CD Process

Our GitHub Actions workflow will:
1. Run tests on every push to the main branch.
2. Build and test the application.
3. Build and push a Docker image if tests pass.
4. Deploy to Docker Hub.

### Required Secrets
For the CI/CD pipeline to deploy to Docker Hub, you need to:

1. Create a Docker Hub access token:
   - Log in to Docker Hub
   - Go to Account Settings > Security > New Access Token
   - Create token with "Read, Write" permissions

2. Add these secrets to your GitHub repository:
   - Go to Repository Settings > Secrets > Actions
   - Add these secrets:
     - `DOCKERHUB_USERNAME`: Your Docker Hub username
     - `DOCKERHUB_TOKEN`: The access token you created

## Contributing

Interested in helping improve the project? See our [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on contributing.


