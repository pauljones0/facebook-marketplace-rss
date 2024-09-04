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
from bs4 import BeautifulSoup
import PyRSS2Gen
from datetime import datetime, timedelta
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
        self.init_selenium()
        self.rss_feed = PyRSS2Gen.RSS2(
            title="Facebook Marketplace Ad Feed",
            link="http://monitor.local/rss",
            description="An RSS feed to monitor new ads on Facebook Marketplace",
            lastBuildDate=self.local_time(datetime.now()),
            items=[]
        )
        
    def set_logger(self):
        """
        Sets up logging configuration.
        """
        self.logger = logging.getLogger(__name__)
        log_formatter = logging.Formatter('%(levelname)s:%(asctime)s:%(funcName)s:%(lineno)d::%(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')
        my_handler = RotatingFileHandler(self.log_filename, mode='w', maxBytes=10*1024*1024, 
                                         backupCount=2, encoding=None, delay=0)
        my_handler.setFormatter(log_formatter)
        my_handler.setLevel(logging.INFO)
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(my_handler)
    
    def init_selenium(self):
        """
        Initializes Selenium WebDriver with Firefox options.
        """
        try:
            self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0"
            self.firefox_options = FirefoxOptions()
            self.firefox_options.add_argument("--headless")
            self.firefox_options.add_argument("--no-sandbox")
            self.firefox_options.add_argument("--disable-dev-shm-usage")
            self.firefox_options.set_preference("general.useragent.override", self.user_agent)
            
            self.gecko_driver_path = GeckoDriverManager().install()
            self.driver = webdriver.Firefox(service=FirefoxService(self.gecko_driver_path), options=self.firefox_options)
            
            # Setup Flask routes
            self.app.add_url_rule('/rss', 'rss', self.rss)
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
                minutes=self.refersh_interval_minutes,
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
        Loads config from a JSON file, where each URL has its own filters.

        Args:
            json_file (str): Path to the JSON file.
        """
        try:
            with open(json_file, 'r') as file:
                data = json.load(file)
                self.server_ip = data['server_ip']
                self.server_port = data['server_port']
                self.currency = data['currency']
                self.refersh_interval_minutes = data['refersh_interval_minutes']
                self.log_filename = data['log_filename']
                self.url_filters = data.get('url_filters', {})
                self.urls_to_monitor = list(self.url_filters.keys())
        except Exception as e:
            self.logger.error(f"Error loading filters from JSON: {e}")
            raise

    def apply_filters(self, url, title):
        """
        Applies keyword filters specific to the URL to the ad title.

        Args:
            url (str): The URL where the ad is found.
            title (str): The title of the ad.

        Returns:
            bool: True if the title matches all filters for the URL, False otherwise.
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
                EC.presence_of_element_located((By.CSS_SELECTOR, 'span'))
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

            for ad_div in soup.find_all('a', class_=True):
                href = ad_div.get('href')
                if not href:
                    continue
                full_url = f"https://facebook.com{href.split('?')[0]}"
                title_span = ad_div.find('span', style=lambda value: value and '-webkit-line-clamp' in value)
                price_span = ad_div.find('span', dir='auto', recursive=True)
                if title_span and price_span:
                    if price_span.get_text(strip=True).startswith(self.currency) or price_span.get_text(strip=True).match('Free'):
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

    def check_for_new_ads(self):
        """
        Checks for new ads on the monitored URLs and updates the RSS feed.
        """
        if not self.job_lock.acquire(blocking=False):
            # Job is still running, skip this run
            self.logger.warning("Previous job still running, skipping this execution.")
            return
        self.logger.info("Fetching new Ads")
        conn = None
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            seven_days_ago = datetime.now() - timedelta(days=7)
            for url in self.urls_to_monitor:
                content = self.get_page_content(url)
                if content is None:
                    continue
                ads = self.extract_ad_details(content, url)
                for ad_id, title, price, ad_url in ads:
                    cursor.execute('''
                    SELECT ad_id FROM ad_changes
                    WHERE ad_id = ? AND last_checked > ?
                ''', (ad_id, seven_days_ago.strftime('%Y-%m-%d %H:%M:%S.%f')))
                    row = cursor.fetchone()
                    if row is None:
                        # self.logger.info(f'New ad detected: {title}')
                        new_item = PyRSS2Gen.RSSItem(
                            title=f"{title} - {price}",
                            link=ad_url,
                            description=f"Price: {price} - {title} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                            guid=PyRSS2Gen.Guid(ad_id),
                            pubDate=self.local_time(datetime.now())
                        )
                        self.rss_feed.items.insert(0, new_item)
                        cursor.execute('INSERT INTO ad_changes (url, ad_id, title, price, last_checked) VALUES (?, ?, ?, ?, ?)',
                                       (ad_url, ad_id, title, price, datetime.now()))
                        conn.commit()
                        self.logger.info(f"New ad detected: {title}")
        except sqlite3.DatabaseError as e:
            self.logger.error(f"Database error: {e}")
        except Exception as e:
            self.logger.error(f"An unexpected error occurred while checking for new ads: {e}")
        finally:
            self.job_lock.release()
            if conn:
                conn.close()

    def generate_rss_feed(self):
        """
        Generates the RSS feed with recent ad changes from the database.
        """
        try:
            self.rss_feed.items = []  # Clear old items
            conn = self.get_db_connection()
            cursor = conn.cursor()
            one_week_ago = datetime.now() - timedelta(days=7)
            cursor.execute('''
                SELECT * FROM ad_changes 
                WHERE last_checked > ? 
                ORDER BY last_checked DESC
            ''', (one_week_ago.strftime('%Y-%m-%d %H:%M:%S'),))
            changes = cursor.fetchall()
            for change in changes:
                try:
                    new_item = PyRSS2Gen.RSSItem(
                        title=f"{change['title']} - {change['price']}",
                        link=change['url'],
                        description=f"Price: {change['price']} - {change['title']} at {change['last_checked']}",
                        guid=PyRSS2Gen.Guid(change['ad_id']),
                        pubDate=self.local_time(datetime.strptime(change['last_checked'], '%Y-%m-%d %H:%M:%S.%f'))
                    )
                    self.rss_feed.items.append(new_item)
                except ValueError as e:
                    self.logger.error(f"Error parsing date from the database: {e}")
            conn.close()
            self.rss_feed.lastBuildDate = self.local_time(datetime.now())
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
    monitor = fbRssAdMonitor(json_file='config.json')
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