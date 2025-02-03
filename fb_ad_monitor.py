"""
Facebook Marketplace RSS Feed Generator

Provides real-time monitoring of Facebook Marketplace ads through RSS feeds.
Handles ad filtering, database storage, and feed generation.

Key Components:
- Selenium-based web scraper
- SQLite database for ad tracking
- RSS feed generation endpoint
- Background job scheduling
- Configurable filtering system

Entry Point:
    main() -> None: Initializes and runs the monitor
"""

# Copyright (c) 2024, regek
# All rights reserved.

# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

from flask import Flask, Response, redirect
import sqlite3
import hashlib
import json
import uuid
import tzlocal
import os
import time
from bs4 import BeautifulSoup
import PyRSS2Gen
from datetime import datetime, timedelta, timezone
from dateutil import parser
import logging
from threading import Lock
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.base import ConflictingIdError
from logging.handlers import RotatingFileHandler
from selenium import webdriver
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from contextlib import contextmanager
from rate_limiter import RateLimiter, rate_limit  # Import the RateLimiter and decorator

class fbRssAdMonitor:
    def __init__(self, json_file):
        """
        Initializes the fbRssAdMonitor instance.

        Args:
            json_file (str): Config json file
        """
        self.urls_to_monitor = []
        self.url_filters = {}  # Dictionary to store filters per URL
        self.database = 'fb-rss-feed.db'
        self.local_tz = tzlocal.get_localzone()

        # Set a default log filename before logging is configured.
        self.log_filename = 'fb-rssfeed.log'
        
        self.set_logger()  # Configure logging early
        self.load_from_json(json_file)  # This should load additional config, including log_level and debug
        
        # Create the Flask app and synchronize its logger level using the configured log_level.
        self.app = Flask(__name__)
        self.app.logger.setLevel(getattr(logging, self.log_level.upper(), logging.INFO))
        
        # Use the configured debug flag for Flask
        self.debug = getattr(self, 'debug', False)
        
        # Set up the rate limiter instance. For example, allow 60 requests per minute per IP.
        limiter = RateLimiter(requests_per_minute=60)

        # Apply rate limiting to the routes by wrapping the view functions.
        self.app.add_url_rule('/', 'home', rate_limit(limiter)(self.home))
        self.app.add_url_rule('/rss', 'rss', rate_limit(limiter)(self.rss))
        
        self.rss_feed = PyRSS2Gen.RSS2(
            title="Facebook Marketplace Ad Feed",
            link="http://monitor.local/rss",
            description="An RSS feed to monitor new ads on Facebook Marketplace",
            lastBuildDate=datetime.now(timezone.utc),
            items=[]
        )

    def set_logger(self):
        """Configures the logger for the fbRssAdMonitor instance.
        
        This implementation wipes the existing log file at startup so that you 
        only see logs from the current run.
        """
        # Wipe out the current log file if it exists
        if os.path.exists(self.log_filename):
            with open(self.log_filename, "w"):
                pass

        self.logger = logging.getLogger("fbRssAdMonitor")
        
        # Remove any existing handlers (in case of reinitialization)
        if self.logger.hasHandlers():
            self.logger.handlers.clear()

        # Set log level (using self.log_level if defined, default to INFO)
        log_level = getattr(logging, self.log_level.upper(), logging.INFO) if hasattr(self, 'log_level') else logging.INFO
        self.logger.setLevel(log_level)

        # Configure a RotatingFileHandler (appending is fine because we cleared the file already)
        handler = RotatingFileHandler(
            self.log_filename,
            mode='a',                 # Append mode (file is already wiped)
            maxBytes=5 * 1024 * 1024,   # 5 MB max per file (adjust as needed)
            backupCount=5             # Keep up to 5 old log files
        )
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def init_selenium(self):
        """Initialize Selenium WebDriver with caching for the geckodriver binary."""
        try:
            remote_url = os.getenv('SELENIUM_REMOTE_URL')
            options = FirefoxOptions()
            options.add_argument("--headless")
            
            if remote_url:
                # Use a remote Selenium instance (e.g., running in a Docker container)
                self.driver = webdriver.Remote(
                    command_executor=remote_url,
                    options=options
                )
            else:
                # For local development, use a cached geckodriver binary if available
                if not hasattr(self, "gecko_path"):
                    self.gecko_path = GeckoDriverManager().install()
                self.driver = webdriver.Firefox(
                    service=FirefoxService(self.gecko_path),
                    options=options
                )
        except Exception as e:
            self.logger.error(f"Error initializing Selenium: {e}")
            raise

    def setup_scheduler(self):
        """
        Setup background job to check new ads immediately and at regular intervals.
        """
        self.job_lock = Lock()
        self.scheduler = BackgroundScheduler()
        try:
            self.scheduler.add_job(
                self.check_for_new_ads,
                'interval',
                id=str(uuid.uuid4()),  # Unique ID for the job
                minutes=self.refresh_interval_minutes,
                next_run_time=datetime.now(),  # Run immediately upon scheduler start
                misfire_grace_time=30,
                coalesce=True
            )
            self.scheduler.start()
        except ConflictingIdError:
            self.logger.warning("Job 'check_ads_job' is already scheduled. Skipping re-schedule.")

    def local_time(self, dt):
        dt.replace(tzinfo=self.local_tz)

    def load_from_json(self, json_file):
        """
        Loads config from a JSON file, where each search has its own filters.

        Args:
            json_file (str): Path to the JSON file.
        """
        try:
            with open(json_file, 'r') as file:
                data = json.load(file)
                self.server_ip = data['server_ip']
                self.server_port = data['server_port']
                self.currency = data['currency']
                self.refresh_interval_minutes = data['refresh_interval_minutes']
                self.request_delay_seconds = data.get('request_delay_seconds')
                self.base_url = data['base_url']
                self.locale = data.get('locale', None)  # Optional locale setting
                self.log_level = data.get('log_level', 'INFO')  # New field for log level
                
                # Convert searches to url_filters format
                self.url_filters = {}
                for search_name, filters in data.get('searches', {}).items():
                    # Start with base URL
                    url = self.base_url
                    
                    # Add locale if specified
                    if self.locale:
                        url = f"{url}/{self.locale}"
                    
                    # Add search query unless it's the default search
                    if search_name != "default":
                        # Get the level1 keywords as they are the main search terms
                        search_terms = filters.get('level1', [])
                        if search_terms:
                            # Join multiple terms with spaces and encode for URL
                            search_query = ' '.join(search_terms)
                            url = f"{url}/search?query={search_query}"
                    
                    self.url_filters[url] = filters
                
                self.urls_to_monitor = list(self.url_filters.keys())
                self.logger.info(f"Loaded {len(self.urls_to_monitor)} URLs to monitor")
                for url in self.urls_to_monitor:
                    self.logger.debug(f"Monitoring URL: {url}")
        except Exception as e:
            self.logger.error(f"Error loading filters from JSON: {e}")
            raise

    def apply_filters(self, url: str, title: str) -> bool:
        self.logger.debug(f"Starting filter check for URL '{url}' with title: '{title}'")
        filters = self.url_filters.get(url, {})
        if not filters:
            self.logger.debug("No filters defined for this URL. Allowing ad.")
            return True

        level_keys = sorted(filters.keys(), key=lambda x: int(x.replace('level', '')))
        for level in level_keys:
            keywords = filters.get(level, [])
            self.logger.debug(f"Filter {level} with keywords {keywords} for title: '{title}'")
            result = any(keyword.lower() in title.lower() for keyword in keywords)
            self.logger.debug(f"Result for {level}: {'passed' if result else 'failed'}")
            if not result:
                self.logger.debug(f"Ad rejected at {level} filter. Title: '{title}' does not contain any of {keywords}")
                return False
        self.logger.debug(f"All filters passed for title: '{title}'")
        return True
    
    def save_html(self, soup):
        html_content = str(soup.prettify())
        # Save the HTML content to a file
        with open('output.html', 'w', encoding='utf-8') as file:
            file.write(html_content)
    
    def get_page_content(self, url):
        """
        Fetches the page content using Selenium.

        Args:
            url (str): The URL of the page to fetch.

        Returns:
            str: The HTML content of the page, or None if an error occurred.
        """
        try:
            self.logger.info(f"Requesting Facebook Marketplace URL: {url}")
            self.driver.get(url)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div.x78zum5.xdt5ytf.x1iyjqo2.xd4ddsz'))
            )
            content = self.driver.page_source
            self.logger.info(f"Successfully fetched page content from {url}. Content length: {len(content)}")
            return content
        except Exception as e:
            self.logger.error(f"An error occurred while fetching page content from {url}: {e}")
            return None

    def get_ads_hash(self, content):
        """
        Generates a hash for the given content.

        Args:
            content (str): The content to hash.

        Returns:
            str: The MD5 hash of the content.
        """
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    def extract_ad_details(self, content, url):
        """
        Extracts ad details from the page content and applies URL-specific filters.

        Args:
            content (str): The HTML content of the page.
            url (str): The URL of the page.

        Returns:
            list: A list of tuples with ad details that match the filters.
        """
        try:
            soup = BeautifulSoup(content, 'html.parser')
            ads = []
            self.save_html(soup)
            for ad_div in soup.find_all('a', class_=True):
                href = ad_div.get('href')
                if not href:
                    continue
                full_url = f"https://facebook.com{href.split('?')[0]}"
                title_span = ad_div.find('span', style=lambda value: value and '-webkit-line-clamp' in value)
                price_span = ad_div.find('span', dir='auto', recursive=True)
                if title_span and price_span:
                    title = title_span.get_text(strip=True)
                    price = price_span.get_text(strip=True)
                    # Only consider ads that have a price starting with the currency (or 'free')
                    if (price.startswith(self.currency) or 'free' in price.lower()) and title != 'No Title' and price != 'No Price':
                        self.logger.debug(f"Raw ad candidate found: title='{title}', price='{price}', url='{full_url}'")
                        # Log filtering before and after
                        if self.apply_filters(url, title):
                            span_id = self.get_ads_hash(full_url)
                            ads.append((span_id, title, price, full_url))
                            self.logger.debug(f"Ad accepted after filtering: [{span_id}] {title} - {price}")
                        else:
                            self.logger.debug(f"Ad rejected after filtering: title='{title}', price='{price}', url='{full_url}'")
            self.logger.debug(f"Total ads found for URL {url}: {len(ads)}. Ads: {ads}")
            return ads
        except Exception as e:
            self.logger.error(f"An error occurred while extracting ad details from URL {url}: {e}")
            return []

    def get_db_connection(self):
        """
        Establishes a connection to the SQLite database.

        Returns:
            sqlite3.Connection: The database connection object.
        """
        try:
            conn = sqlite3.connect(self.database)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as e:
            self.logger.error(f"Database connection error: {e}")
            raise

    def process_single_ad(self, cursor: sqlite3.Cursor, ad_details: tuple, seven_days_ago: datetime) -> None:
        ad_id, title, price, ad_url = ad_details
        
        if not self._is_ad_recent(cursor, ad_id, seven_days_ago):
            try:
                new_item = self._create_rss_item(title, price, ad_url, ad_id)
                self._save_ad_to_database(cursor, ad_url, ad_id, title, price)
                self.rss_feed.items.insert(0, new_item)
                self.logger.info(f"New ad detected: {title}")
            except sqlite3.IntegrityError:
                pass

    def _is_ad_recent(self, cursor: sqlite3.Cursor, ad_id: str, seven_days_ago: datetime) -> bool:
        cursor.execute('''
            SELECT ad_id FROM ad_changes
            WHERE ad_id = ? AND last_checked > ?
        ''', (ad_id, seven_days_ago.isoformat()))
        return cursor.fetchone() is not None

    def _create_rss_item(self, title: str, price: str, ad_url: str, ad_id: str) -> PyRSS2Gen.RSSItem:
        current_time = datetime.now(timezone.utc)
        return PyRSS2Gen.RSSItem(
            title=f"{title} - {price}",
            link=ad_url,
            description=f"Price: {price} - {title} at {current_time}",
            guid=PyRSS2Gen.Guid(ad_id),
            pubDate=self.local_time(current_time)
        )

    def _save_ad_to_database(self, cursor: sqlite3.Cursor, ad_url: str, ad_id: str, 
                            title: str, price: str) -> None:
        cursor.execute('''
            INSERT INTO ad_changes (url, ad_id, title, price, last_checked) 
            VALUES (?, ?, ?, ?, ?)
        ''', (ad_url, ad_id, title, price, datetime.now(timezone.utc).isoformat()))

    def get_request_delay(self) -> float:
        """
        Determines the delay between URL requests.
        Uses the manual override from the config if specified; otherwise,
        calculates a delay based on the number of URLs.
        
        Returns:
            float: Delay in seconds.
        """
        if hasattr(self, "request_delay_seconds") and self.request_delay_seconds is not None:
            return self.request_delay_seconds
        num_urls = len(self.urls_to_monitor)
        if num_urls <= 5:
            return 2.0
        elif num_urls >= 10:
            return 10.0
        else:
            # Linear interpolation between 2 and 10 seconds for 5-10 URLs:
            return 2.0 + (num_urls - 5) * ((10.0 - 2.0) / 5.0)

    def check_for_new_ads(self):
        """
        Checks for new ads on the monitored URLs and updates the RSS feed.
        """
        if not self.job_lock.acquire(blocking=False):
            self.logger.warning("Previous job still running, skipping this execution.")
            return

        self.logger.info("Starting new ads check job.")
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
                # Initialize the driver once for all URLs
                self.init_selenium()
                for url in self.urls_to_monitor:
                    self.logger.info(f"Processing URL: {url}")
                    try:
                        content = self.get_page_content(url)
                        if content:
                            ads = self.extract_ad_details(content, url)
                            self.logger.info(f"URL {url} yielded {len(ads)} ads after filtering.")
                            for ad_details in ads:
                                self.process_single_ad(cursor, ad_details, seven_days_ago)
                            conn.commit()
                        else:
                            self.logger.error(f"No content returned for {url}")
                    except Exception as e:
                        self.logger.error(f"Error processing URL {url}: {e}")
                    finally:
                        delay = self.get_request_delay()
                        time.sleep(delay)
        except Exception as e:
            self.logger.error(f"An unexpected error occurred while checking for new ads: {e}")
        finally:
            if hasattr(self, 'driver') and self.driver:
                self.driver.quit()  # Close the Selenium driver
            self.job_lock.release()

    def generate_rss_feed(self):
        """
        Generates the RSS feed with recent ad changes from the database.
        """
        try:
            self.rss_feed.items = []  # Clear old items
            conn = self.get_db_connection()
            cursor = conn.cursor()
            # one_week_ago = datetime.now(timezone.utc) - timedelta(minutes=self.refresh_interval_minutes+5)
            # print(one_week_ago)
            cursor.execute('''
                SELECT * FROM ad_changes 
                WHERE last_checked > ? 
                ORDER BY last_checked DESC
            ''', (self.rss_feed.lastBuildDate.isoformat(),))
            changes = cursor.fetchall()
            for change in changes:
                try:
                    last_checked_datetime = parser.parse(change['last_checked'])
                    new_item = PyRSS2Gen.RSSItem(
                        title=f"{change['title']} - {change['price']}",
                        link=change['url'],
                        description=f"Price: {change['price']} - {change['title']} at {change['last_checked']}",
                        guid=PyRSS2Gen.Guid(change['ad_id']),
                        pubDate=self.local_time(last_checked_datetime)
                    )
                    self.rss_feed.items.append(new_item)
                except ValueError as e:
                    self.logger.error(f"Error parsing date from the database: {e}")
            conn.close()
            self.rss_feed.lastBuildDate = datetime.now(timezone.utc)
        except sqlite3.DatabaseError as e:
            self.logger.error(f"Database error while generating RSS feed: {e}")
        except Exception as e:
            self.logger.error(f"An unexpected error occurred while generating RSS feed: {e}")

    def rss(self):
        """
        Returns the RSS feed as a Flask Response object.
        
        Returns:
            flask.Response: The RSS feed in XML format.
        """
        self.generate_rss_feed()
        return Response(self.rss_feed.to_xml(encoding='utf-8'), mimetype='application/rss+xml')

    def home(self):
        """Redirect the home page to the /rss endpoint."""
        return redirect('/rss')

    def run(self):
        """
        Starts the Flask application and scheduler.
        """
        try:
            self.app.run(
                host=self.server_ip,
                port=int(self.server_port),
                debug=self.debug
            )
        except (KeyboardInterrupt, SystemExit):
            self.scheduler.shutdown()
        finally:
            if hasattr(self, 'driver') and self.driver:
                self.driver.quit()

if __name__ == "__main__":
    # Initialize and run the ad monitor
    config_file = os.getenv('CONFIG_FILE', 'config.json')
    if not os.path.exists(config_file):
        print(f'Error: Config file {config_file} not found!!!')
        exit()
    monitor = fbRssAdMonitor(json_file=config_file)
    monitor.setup_scheduler()
    monitor.run()


# Example JSON structure for URL-specific filters
# {
#     "url_filters": {
#         "https://example.com/page1": {
#             "level1": ["tv"],
#             "level2": ["smart"],
#             "level3": ["55\"", "55 inch"]
#         },
#         "https://example.com/page2": {
#             "level1": ["tv"],
#             "level2": ["4k"],
#             "level3": ["65\"", "65 inch"]
#         }
#     }
# }