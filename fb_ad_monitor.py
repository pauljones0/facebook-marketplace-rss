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

from flask import Flask, Response
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

class fbRssAdMonitor:
    def __init__(self, json_file):
        """
        Initializes the fbRssAdMonitor instance.

        Args:
            json_file (str): Config json file
        """
        self.urls_to_monitor = []
        self.url_filters = {}  # Dictionary to store filters per URL
        self.database='fb-rss-feed.db'
        self.local_tz = tzlocal.get_localzone()

        self.load_from_json(json_file)
        self.set_logger()
        self.app = Flask(__name__)
        self.app.add_url_rule('/rss', 'rss', self.rss)
        self.rss_feed = PyRSS2Gen.RSS2(
            title="Facebook Marketplace Ad Feed",
            link="http://monitor.local/rss",
            description="An RSS feed to monitor new ads on Facebook Marketplace",
            lastBuildDate=datetime.now(timezone.utc),
            items=[]
        )

    def set_logger(self):
        """
        Sets up logging configuration with both file and console streaming.
        Log level is fetched from the environment variable LOG_LEVEL.
        """
        self.logger = logging.getLogger(__name__)
        log_formatter = logging.Formatter('%(levelname)s:%(asctime)s:%(funcName)s:%(lineno)d::%(message)s', 
                                          datefmt='%m/%d/%Y %I:%M:%S %p')

        # Get log level from environment variable, defaulting to INFO if not set
        log_level_str = os.getenv('LOG_LEVEL', 'INFO').upper()
        log_level = logging.getLevelName(log_level_str)

        # File handler (rotating log)
        file_handler = RotatingFileHandler(self.log_filename, mode='w', maxBytes=10*1024*1024, 
                                           backupCount=2, encoding=None, delay=0)
        file_handler.setFormatter(log_formatter)
        file_handler.setLevel(log_level)

        # Stream handler (console output)
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(log_formatter)
        console_handler.setLevel(log_level)

        # Set the logger level and add handlers
        self.logger.setLevel(log_level)
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    
    def init_selenium(self):
        """Initialize Selenium WebDriver with container support."""
        try:
            remote_url = os.getenv('SELENIUM_REMOTE_URL')
            
            if remote_url:
                # Use containerized Selenium
                options = webdriver.FirefoxOptions()
                options.add_argument("--headless")
                self.driver = webdriver.Remote(
                    command_executor=remote_url,
                    options=options
                )
            else:
                # Local development setup
                options = FirefoxOptions()
                options.add_argument("-headless")
                self.driver = webdriver.Firefox(
                    service=FirefoxService(GeckoDriverManager().install()),
                    options=options
                )
        except Exception as e:
            self.logger.error(f"Error initializing Selenium: {e}")
            raise

    def setup_scheduler(self):
        """
        Setup background job to check new ads
        """
        self.job_lock = Lock()
        self.scheduler = BackgroundScheduler()
        try:
            self.scheduler.add_job(
                self.check_for_new_ads,
                'interval',
                id=str(uuid.uuid4()),  # Unique ID for the job
                minutes=self.refresh_interval_minutes,
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
                self.log_filename = data['log_filename']
                self.base_url = data['base_url']
                self.locale = data.get('locale', None)  # Optional locale setting
                
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
        """Filter ads based on URL-specific rules.
        
        Args:
            url: Marketplace URL where ad was found
            title: Ad title text
            
        Returns:
            True if ad matches all filters
            
        Raises:
            KeyError: If URL not in filters
        """
        filters = self.url_filters.get(url, {})
        if not filters:
            return True

        try:
            # Iterate through filter levels in order
            level_keys = sorted(filters.keys(), key=lambda x: int(x.replace('level', '')))  # Sort levels numerically
            # print (f"{title} - {level_keys}")
            for level in level_keys:
                keywords = filters.get(level, [])
                # print (f"{title} - {level} - {keywords}")
                if not any(keyword.lower() in title.lower() for keyword in keywords):
                    return False  # If any level fails, return False
        except Exception as e:
            self.logger.error(f"An error while processing filters for {title}",e)
            return False
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
            self.logger.info(f"Requesting {url}")
            self.driver.get(url)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div.x78zum5.xdt5ytf.x1iyjqo2.xd4ddsz'))
            )
            return self.driver.page_source
        except Exception as e:
            self.logger.error(f"An error occurred while fetching page content: {e}")
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
                # print(title_span)
                # print(price_span)
                if title_span and price_span:
                    if price_span.get_text(strip=True).startswith(self.currency) or 'free' in price_span.get_text(strip=True).lower():
                        title = title_span.get_text(strip=True) if title_span else 'No Title'
                        price = price_span.get_text(strip=True) if price_span else 'No Price'

                        if title != 'No Title' and price != 'No Price':
                            span_id = self.get_ads_hash(full_url)
                            if self.apply_filters(url, title):
                                ads.append((span_id, title, price, full_url))
            
            return ads
        except Exception as e:
            self.logger.error(f"An error occurred while extracting ad details: {e}")
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

    def check_for_new_ads(self):
        """
        Checks for new ads on the monitored URLs and updates the RSS feed.
        """
        if not self.job_lock.acquire(blocking=False):
            self.logger.warning("Previous job still running, skipping this execution.")
            return

        self.logger.info("Fetching new Ads")
        try:
            with get_db_connection(self.database) as conn:
                cursor = conn.cursor()
                seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
                
                for url in self.urls_to_monitor:
                    try:
                        self.init_selenium()
                        if content := self.get_page_content(url):
                            ads = self.extract_ad_details(content, url)
                            for ad_details in ads:
                                self.process_single_ad(cursor, ad_details, seven_days_ago)
                            conn.commit()
                    finally:
                        self.driver.quit()
                        time.sleep(2)
        except Exception as e:
            self.logger.error(f"An unexpected error occurred while checking for new ads: {e}")
        finally:
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

    def run(self, debug_opt=False):
        """
        Starts the Flask application and scheduler.

        Args:
            debug_opt (bool, optional): Debug mode option for Flask. Defaults to False.
        """
        try:
            self.app.run(host=self.server_ip, port=self.server_port, debug=debug_opt)
        except (KeyboardInterrupt, SystemExit):
            self.scheduler.shutdown()
        finally:
            self.driver.quit()  # Close the Selenium driver

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