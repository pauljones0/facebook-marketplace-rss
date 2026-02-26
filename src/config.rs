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
}
