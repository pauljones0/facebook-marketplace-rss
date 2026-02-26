use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::path::Path;

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct Config {
    pub server_ip: String,
    pub server_port: u16,
    pub currency: String,
    pub refresh_interval_minutes: u64,
    pub log_filename: String,
    pub database_name: String,
    pub url_filters: HashMap<String, HashMap<String, Vec<String>>>,
}

impl Config {
    pub fn load<P: AsRef<Path>>(path: P) -> Result<Self> {
        let content = fs::read_to_string(path)?;
        let config: Config = serde_json::from_str(&content)?;
        Ok(config)
    }

    pub fn save<P: AsRef<Path>>(&self, path: P) -> Result<()> {
        let content = serde_json::to_string_pretty(self)?;
        fs::write(path, content)?;
        Ok(())
    }

    pub fn validate(&self) -> Result<()> {
        if self.server_port == 0 {
            return Err(anyhow::anyhow!("Server port must be greater than 0"));
        }
        if self.refresh_interval_minutes == 0 {
            return Err(anyhow::anyhow!("Refresh interval must be greater than 0"));
        }

        for (url_str, filters) in &self.url_filters {
            let parsed_url = url::Url::parse(url_str)
                .map_err(|_| anyhow::anyhow!("Invalid URL format: {}", url_str))?;
            if parsed_url.scheme().is_empty() || parsed_url.host_str().unwrap_or("").is_empty() {
                return Err(anyhow::anyhow!("Invalid URL format: {}", url_str));
            }

            for level_name in filters.keys() {
                if !level_name.starts_with("level")
                    || !level_name[5..].chars().all(|c| c.is_ascii_digit())
                    || level_name.len() <= 5
                {
                    return Err(anyhow::anyhow!(
                        "Invalid filter level name '{}' for URL '{}'",
                        level_name,
                        url_str
                    ));
                }
            }
        }

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;
    use tempfile::NamedTempFile;

    #[test]
    fn test_load_config() {
        let config_json = r#"{
            "server_ip": "127.0.0.1",
            "server_port": 5000,
            "currency": "$",
            "refresh_interval_minutes": 15,
            "log_filename": "test.log",
            "database_name": "test.db",
            "url_filters": {
                "https://example.com": {
                    "level1": ["keyword1", "keyword2"]
                }
            }
        }"#;

        let mut tmpfile = NamedTempFile::new().unwrap();
        write!(tmpfile, "{}", config_json).unwrap();

        let config = Config::load(tmpfile.path()).unwrap();
        assert_eq!(config.server_ip, "127.0.0.1");
        assert_eq!(config.server_port, 5000);
        assert_eq!(
            config
                .url_filters
                .get("https://example.com")
                .unwrap()
                .get("level1")
                .unwrap()[0],
            "keyword1"
        );
    }

    #[test]
    fn test_save_config() {
        let config = Config {
            server_ip: "127.0.0.1".to_string(),
            server_port: 5000,
            currency: "$".to_string(),
            refresh_interval_minutes: 15,
            log_filename: "test.log".to_string(),
            database_name: "test.db".to_string(),
            url_filters: HashMap::new(),
        };

        let tmpfile = NamedTempFile::new().unwrap();
        config.save(tmpfile.path()).unwrap();

        let loaded = Config::load(tmpfile.path()).unwrap();
        assert_eq!(loaded.server_ip, "127.0.0.1");
    }

    #[test]
    fn test_validate_config() {
        let mut config = Config {
            server_ip: "127.0.0.1".to_string(),
            server_port: 5000,
            currency: "$".to_string(),
            refresh_interval_minutes: 15,
            log_filename: "test.log".to_string(),
            database_name: "test.db".to_string(),
            url_filters: HashMap::new(),
        };

        assert!(config.validate().is_ok());

        config.server_port = 0;
        assert!(config.validate().is_err());
        config.server_port = 5000;

        config.refresh_interval_minutes = 0;
        assert!(config.validate().is_err());
        config.refresh_interval_minutes = 15;

        let mut invalid_url_filters = HashMap::new();
        invalid_url_filters.insert("not-a-url".to_string(), HashMap::new());
        config.url_filters = invalid_url_filters;
        assert!(config.validate().is_err());

        let mut valid_url_filters = HashMap::new();
        let mut filters = HashMap::new();
        filters.insert("invalid-level".to_string(), vec!["keyword".to_string()]);
        valid_url_filters.insert(
            "https://facebook.com/marketplace/item/1".to_string(),
            filters,
        );
        config.url_filters = valid_url_filters;
        assert!(config.validate().is_err());

        let mut valid_url_filters_with_valid_levels = HashMap::new();
        let mut filters = HashMap::new();
        filters.insert("level1".to_string(), vec!["keyword".to_string()]);
        valid_url_filters_with_valid_levels.insert(
            "https://facebook.com/marketplace/item/1".to_string(),
            filters,
        );
        config.url_filters = valid_url_filters_with_valid_levels;
        assert!(config.validate().is_ok());
    }
}
