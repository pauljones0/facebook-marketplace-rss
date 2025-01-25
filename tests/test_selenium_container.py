import os
import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

@pytest.mark.selenium_container
def test_selenium_container_connection():
    options = webdriver.FirefoxOptions()
    options.add_argument("--headless")
    
    driver = webdriver.Remote(
        command_executor=os.getenv('SELENIUM_REMOTE_URL', 'http://localhost:4444/wd/hub'),
        options=options
    )
    
    try:
        driver.get("https://www.facebook.com/marketplace")
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, 'body'))
        )
        assert "Marketplace" in driver.title
    finally:
        driver.quit() 