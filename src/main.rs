use crate::config::Config;
use crate::db::{AdEntry, Database};
use crate::filter::apply_filters;
use crate::scraper::{extract_ads, Scraper};
use crate::web::{app, AppState};
use anyhow::Result;
use backoff::backoff::Backoff;
use backoff::ExponentialBackoff;
use std::sync::Arc;
use tokio::sync::RwLock;
use tokio::time::{sleep, Duration};
use tracing::{error, info, warn};
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

mod config;
mod db;
mod filter;
mod rss_gen;
mod scraper;
mod web;

async fn check_for_ads(state: Arc<AppState>) -> Result<()> {
    let config = state.config.read().await.clone();
    let urls: Vec<_> = config.url_filters.keys().cloned().collect();
    if urls.is_empty() {
        return Ok(());
    }

    let num_scrapers = std::cmp::min(3, urls.len());
    let mut chunks = vec![Vec::new(); num_scrapers];
    for (i, url) in urls.into_iter().enumerate() {
        chunks[i % num_scrapers].push(url);
    }

    let mut tasks = Vec::new();

    for chunk in chunks {
        let config_clone = config.clone();
        let state_clone = Arc::clone(&state);

        let task = tokio::spawn(async move {
            let mut scraper = Scraper::new();
            let mut backoff = ExponentialBackoff {
                max_elapsed_time: Some(Duration::from_secs(60)),
                ..Default::default()
            };

            // Init scraper with retry
            let mut init_success = false;
            while let Some(delay) = backoff.next_backoff() {
                match scraper.init().await {
                    Ok(_) => {
                        init_success = true;
                        break;
                    }
                    Err(e) => {
                        warn!(
                            "Failed to init scraper, retrying in {:?}... Error: {}",
                            delay, e
                        );
                        sleep(delay).await;
                    }
                }
            }

            if !init_success {
                error!("Failed to initialize scraper after retries");
                return;
            }

            for url in chunk {
                info!("Processing URL: {}", url);

                let mut fetch_backoff = backoff.clone();
                fetch_backoff.reset();
                let mut content = None;

                while let Some(delay) = fetch_backoff.next_backoff() {
                    match scraper.get_page_content(&url).await {
                        Ok(c) => {
                            content = Some(c);
                            break;
                        }
                        Err(e) => {
                            warn!(
                                "Failed to fetch content for {}, retrying in {:?}... Error: {}",
                                url, delay, e
                            );
                            sleep(delay).await;
                        }
                    }
                }

                let Some(content) = content else {
                    error!("Failed to fetch content for {} after retries", url);
                    continue;
                };

                let ads = extract_ads(&content, &config_clone.currency);
                for (id, title, price, ad_url) in ads {
                    if apply_filters(&config_clone.url_filters, &url, &title) {
                        let entry = AdEntry {
                            ad_id: id,
                            title,
                            price,
                            url: ad_url,
                            first_seen: chrono::Utc::now(),
                            last_checked: chrono::Utc::now(),
                        };
                        match state_clone.db.insert_or_update_ad(&entry) {
                            Ok(is_new) => {
                                if is_new {
                                    info!("New ad found: {}", entry.title);
                                }
                            }
                            Err(e) => error!("Failed to save ad: {}", e),
                        }
                    }
                }

                let delay = rand::random_range(2..10);
                sleep(Duration::from_secs(delay)).await;
            }

            let _ = scraper.quit().await;
        });

        tasks.push(task);
    }

    for task in tasks {
        let _ = task.await;
    }

    let _ = state.db.prune_old_ads(14);
    Ok(())
}

#[tokio::main]
async fn main() -> Result<()> {
    let config_path = std::env::var("CONFIG_FILE").unwrap_or_else(|_| "config.json".to_string());

    // Load config first to get log filename
    let config = match Config::load(&config_path) {
        Ok(c) => c,
        Err(_) => {
            // Fallback config for tracing init if file missing
            Config {
                server_ip: "0.0.0.0".to_string(),
                server_port: 5000,
                currency: "$".to_string(),
                refresh_interval_minutes: 15,
                log_filename: "fb-rssfeed.log".to_string(),
                database_name: "fb-rss-feed.db".to_string(),
                url_filters: std::collections::HashMap::new(),
            }
        }
    };

    // Initialize tracing with file rotation
    let file_appender = tracing_appender::rolling::daily(".", &config.log_filename);
    let (non_blocking, _guard) = tracing_appender::non_blocking(file_appender);

    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::from_default_env()
                .add_directive(tracing::Level::INFO.into()),
        )
        .with(tracing_subscriber::fmt::layer()) // Console
        .with(tracing_subscriber::fmt::layer().with_writer(non_blocking)) // File
        .init();

    info!("Configuration loaded from {}", config_path);
    let db = Database::new(&config.database_name)?;

    let server_ip = config.server_ip.clone();
    let server_port = config.server_port;

    let state = Arc::new(AppState {
        config: RwLock::new(config.clone()),
        db,
        start_time: std::time::Instant::now(),
        config_path: config_path.clone(),
    });

    // Start background task
    let bg_state = Arc::clone(&state);
    tokio::spawn(async move {
        loop {
            let interval = {
                let c = bg_state.config.read().await;
                c.refresh_interval_minutes
            };

            if let Err(e) = check_for_ads(Arc::clone(&bg_state)).await {
                error!("Error in background ad check: {}", e);
            }

            info!("Sleeping for {} minutes...", interval);
            sleep(Duration::from_secs(interval * 60)).await;
        }
    });

    info!("Starting server on {}:{}", server_ip, server_port);
    let listener = tokio::net::TcpListener::bind(format!("{}:{}", server_ip, server_port)).await?;

    // Graceful shutdown listener
    let server = axum::serve(listener, app(state)).with_graceful_shutdown(async {
        tokio::signal::ctrl_c()
            .await
            .expect("failed to install CTRL+C handler");
        info!("Shutdown signal received");
    });

    server.await?;

    info!("Server shutdown complete");
    Ok(())
}

#[cfg(test)]
mod e2e_tests {
    use super::*;
    use crate::config::Config;
    use reqwest::Client;
    use std::time::Duration;
    use tempfile::NamedTempFile;

    #[tokio::test]
    async fn test_api_e2e() {
        let db_file = NamedTempFile::new().unwrap();
        let db_path = db_file.path().to_str().unwrap().to_string();

        let config = Config {
            server_ip: "127.0.0.1".to_string(),
            server_port: 0, // OS assigns random free port
            currency: "$".to_string(),
            refresh_interval_minutes: 15,
            log_filename: "test.log".to_string(),
            database_name: db_path,
            url_filters: std::collections::HashMap::new(),
        };

        let db = Database::new(&config.database_name).unwrap();
        let config_file = NamedTempFile::new().unwrap();
        let config_path = config_file.path().to_str().unwrap().to_string();

        let state = Arc::new(AppState {
            config: RwLock::new(config.clone()),
            db,
            start_time: std::time::Instant::now(),
            config_path,
        });

        let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
        let port = listener.local_addr().unwrap().port();

        // Spawn the server
        tokio::spawn(async move {
            axum::serve(listener, app(state)).await.unwrap();
        });

        // Give server a moment to start
        tokio::time::sleep(Duration::from_millis(100)).await;

        let client = Client::new();
        let base_url = format!("http://127.0.0.1:{}", port);

        // Test health check
        let resp = client
            .get(format!("{}/health", base_url))
            .send()
            .await
            .unwrap();
        assert!(resp.status().is_success());
        let health_json: serde_json::Value = resp.json().await.unwrap();
        assert_eq!(health_json["status"], "up");

        // Test get config
        let resp = client
            .get(format!("{}/api/config", base_url))
            .send()
            .await
            .unwrap();
        assert!(resp.status().is_success());
        let returned_config: Config = resp.json().await.unwrap();
        assert_eq!(returned_config.currency, "$");

        // Test update config (invalid)
        let mut new_config = returned_config.clone();
        new_config.server_port = 0;
        let resp = client
            .post(format!("{}/api/config", base_url))
            .json(&new_config)
            .send()
            .await
            .unwrap();
        assert_eq!(resp.status().as_u16(), 400);

        // Test update config (valid)
        new_config.server_port = 9000;
        let resp = client
            .post(format!("{}/api/config", base_url))
            .json(&new_config)
            .send()
            .await
            .unwrap();
        assert_eq!(resp.status().as_u16(), 200);
    }
}
