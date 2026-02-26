use crate::config::Config;
use crate::db::{AdEntry, Database};
use crate::filter::apply_filters;
use crate::scraper::{extract_ads, Scraper};
use crate::web::{app, AppState};
use anyhow::Result;
use std::sync::Arc;
use tokio::sync::RwLock;
use tokio::time::{sleep, Duration};
use tracing::{error, info};
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

mod config;
mod db;
mod filter;
mod rss_gen;
mod scraper;
mod web;

async fn check_for_ads(state: Arc<AppState>, scraper: &mut Scraper) -> Result<()> {
    let config = state.config.read().await.clone();

    for url in config.url_filters.keys() {
        info!("Processing URL: {}", url);
        // Scraper is already initialized in the loop outside

        match scraper.get_page_content(url).await {
            Ok(content) => {
                let ads = extract_ads(&content, &config.currency);
                for (id, title, price, ad_url) in ads {
                    if apply_filters(&config.url_filters, url, &title) {
                        let entry = AdEntry {
                            ad_id: id,
                            title,
                            price,
                            url: ad_url,
                            first_seen: chrono::Utc::now(),
                            last_checked: chrono::Utc::now(),
                        };
                        match state.db.insert_or_update_ad(&entry) {
                            Ok(is_new) => {
                                if is_new {
                                    info!("New ad found: {}", entry.title);
                                }
                            }
                            Err(e) => error!("Failed to save ad: {}", e),
                        }
                    }
                }
            }
            Err(e) => error!("Failed to fetch content for {}: {}", url, e),
        }

        // Random jitter delay
        let delay = rand::random_range(2..10);
        sleep(Duration::from_secs(delay)).await;
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
    });

    // Start background task
    let bg_state = Arc::clone(&state);
    tokio::spawn(async move {
        let mut scraper = Scraper::new();
        loop {
            let interval = {
                let c = bg_state.config.read().await;
                c.refresh_interval_minutes
            };

            // Re-init scraper if needed (e.g. if it crashed or was quit)
            if let Err(e) = scraper.init().await {
                error!("Failed to init scraper: {}. Retrying later.", e);
                sleep(Duration::from_secs(60)).await;
                continue;
            }

            if let Err(e) = check_for_ads(Arc::clone(&bg_state), &mut scraper).await {
                error!("Error in background ad check: {}", e);
            }

            let _ = scraper.quit().await;

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
