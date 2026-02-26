use anyhow::{anyhow, Result};
use md5;
use scraper::{Html, Selector};
use thirtyfour::prelude::*;

pub struct Scraper {
    driver: Option<WebDriver>,
}

impl Scraper {
    pub fn new() -> Self {
        Scraper { driver: None }
    }

    pub async fn init(&mut self) -> Result<()> {
        let mut caps = DesiredCapabilities::firefox();
        caps.add_arg("--headless")?;
        caps.add_arg("--no-sandbox")?;
        caps.add_arg("--disable-dev-shm-usage")?;

        // Match Python's user agent randomization if possible, or use a stable one
        caps.add_arg("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")?;

        let driver = WebDriver::new("http://localhost:4444", caps).await?;
        self.driver = Some(driver);
        Ok(())
    }

    pub async fn quit(&mut self) -> Result<()> {
        if let Some(driver) = self.driver.take() {
            driver.quit().await?;
        }
        Ok(())
    }

    pub async fn get_page_content(&self, url: &str) -> Result<String> {
        let driver = self
            .driver
            .as_ref()
            .ok_or_else(|| anyhow!("Driver not initialized"))?;
        driver.goto(url).await?;

        // Check for redirect to login (soft block detection)
        let current_url = driver.current_url().await?.to_string().to_lowercase();
        if current_url.contains("login") || current_url.contains("checkpoint") {
            return Err(anyhow!(
                "Potential soft block detected: redirected to {}",
                current_url
            ));
        }

        // Wait for ads to load (timeout 20s as in Python)
        let _ = driver
            .query(By::Css("div[role='main'] div.x87ps6o"))
            .first()
            .await?;

        let source = driver.source().await?;
        Ok(source)
    }
}

pub fn extract_ads(html_content: &str) -> Vec<(String, String, String, String)> {
    let document = Html::parse_document(html_content);
    let ad_link_selector = Selector::parse("a[href^='/marketplace/item/']").unwrap();
    let title_selector = Selector::parse("span[style*='-webkit-line-clamp']").unwrap();
    let price_selector = Selector::parse("span[dir='auto']").unwrap();

    let mut ads = Vec::new();
    let mut processed_urls = std::collections::HashSet::new();

    for ad_link in document.select(&ad_link_selector) {
        let href = match ad_link.value().attr("href") {
            Some(h) => h.split('?').next().unwrap_or(h),
            None => continue,
        };

        let full_url = format!("https://facebook.com{}", href);
        if !processed_urls.insert(full_url.clone()) {
            continue;
        }

        let title = ad_link
            .select(&title_selector)
            .next()
            .map(|el| el.text().collect::<String>().trim().to_string());

        let price = ad_link
            .select(&price_selector)
            .next()
            .map(|el| el.text().collect::<String>().trim().to_string());

        if let (Some(t), Some(p)) = (title, price) {
            // Validate price starts with currency or is free (similar to Python logic)
            if p.starts_with('$') || p.to_lowercase().contains("free") {
                let id_hash = get_ad_hash(&full_url);
                ads.push((id_hash, t, p, full_url));
            }
        }
    }

    ads
}

pub fn get_ad_hash(url: &str) -> String {
    format!("{:x}", md5::compute(url))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_extract_ads_single() {
        let html = r#"
            <a href="/marketplace/item/123456789/?ref=search">
                <span style="-webkit-line-clamp: 2;">Awesome iPhone 15</span>
                <span dir="auto">$800</span>
            </a>
        "#;
        let ads = extract_ads(html);
        assert_eq!(ads.len(), 1);
        let (_hash, title, price, url) = &ads[0];
        assert_eq!(title, "Awesome iPhone 15");
        assert_eq!(price, "$800");
        assert!(url.contains("123456789"));
    }

    #[test]
    fn test_extract_ads_none() {
        let html = "<div>No ads here</div>";
        let ads = extract_ads(html);
        assert_eq!(ads.len(), 0);
    }

    #[test]
    fn test_extract_ads_multiple() {
        let html = r#"
            <div>
                <a href="/marketplace/item/111/?ref=search">
                    <span style="-webkit-line-clamp: 2;">Item 1</span>
                    <span dir="auto">$10</span>
                </a>
                <a href="/marketplace/item/222/?ref=search">
                    <span style="-webkit-line-clamp: 2;">Item 2</span>
                    <span dir="auto">$20</span>
                </a>
            </div>
        "#;
        let ads = extract_ads(html);
        assert_eq!(ads.len(), 2);
    }
}
