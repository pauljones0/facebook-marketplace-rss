use crate::config::Config;
use crate::db::Database;
use axum::{
    extract::State,
    response::{IntoResponse, Response},
    routing::get,
    Json, Router,
};
use chrono::Utc;
use serde_json::json;
use std::sync::Arc;
use tokio::sync::RwLock;
use tower_http::services::ServeDir;

pub struct AppState {
    pub config: RwLock<Config>,
    pub db: Database,
    pub start_time: std::time::Instant,
    pub config_path: String,
}

pub fn app(state: Arc<AppState>) -> Router {
    Router::new()
        .route("/health", get(health_check))
        .route("/rss", get(rss_feed))
        .route("/edit", get(edit_config_page))
        .route("/api/config", get(get_config).post(update_config))
        .nest_service("/static", ServeDir::new("static"))
        .with_state(state)
}

async fn edit_config_page() -> impl IntoResponse {
    let html = match std::fs::read_to_string("templates/edit_config.html") {
        Ok(h) => h,
        Err(_) => return (axum::http::StatusCode::NOT_FOUND, "Template not found").into_response(),
    };
    axum::response::Html(html).into_response()
}

async fn health_check(State(state): State<Arc<AppState>>) -> impl IntoResponse {
    let config = state.config.read().await;
    let uptime_secs = state.start_time.elapsed().as_secs();
    let status = json!({
        "status": "up",
        "timestamp": Utc::now().to_rfc3339(),
        "database": config.database_name,
        "uptime_secs": uptime_secs,
    });
    Json(status)
}

async fn rss_feed(State(state): State<Arc<AppState>>) -> Response {
    let ads = match state.db.get_recent_ads(7) {
        Ok(a) => a,
        Err(_) => {
            return (
                axum::http::StatusCode::INTERNAL_SERVER_ERROR,
                "Database error",
            )
                .into_response()
        }
    };

    let config = state.config.read().await;
    match crate::rss_gen::generate_rss(&ads, &config.server_ip, config.server_port) {
        Ok(xml) => Response::builder()
            .header("content-type", "application/rss+xml")
            .body(axum::body::Body::from(xml))
            .unwrap(),
        Err(_) => (
            axum::http::StatusCode::INTERNAL_SERVER_ERROR,
            "RSS generation error",
        )
            .into_response(),
    }
}

async fn get_config(State(state): State<Arc<AppState>>) -> impl IntoResponse {
    let config = state.config.read().await;
    Json(config.clone())
}

async fn update_config(
    State(state): State<Arc<AppState>>,
    Json(new_config): Json<Config>,
) -> impl IntoResponse {
    if let Err(e) = new_config.validate() {
        tracing::error!("Invalid config: {}", e);
        return (
            axum::http::StatusCode::BAD_REQUEST,
            Json(json!({"detail": e.to_string()})),
        )
            .into_response();
    }

    // Save to disk
    if let Err(e) = new_config.save(&state.config_path) {
        tracing::error!("Failed to save config: {}", e);
        return (
            axum::http::StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({"detail": format!("Failed to save config: {}", e)})),
        )
            .into_response();
    }

    // Update shared state
    let mut config = state.config.write().await;
    *config = new_config;

    (
        axum::http::StatusCode::OK,
        Json(json!({"message": "Configuration saved successfully!"})),
    )
        .into_response()
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::body::Body;
    use axum::http::StatusCode;
    use tower::ServiceExt;

    fn make_state() -> Arc<AppState> {
        let config = Config {
            server_ip: "127.0.0.1".to_string(),
            server_port: 5000,
            currency: "$".to_string(),
            refresh_interval_minutes: 15,
            log_filename: "test.log".to_string(),
            database_name: ":memory:".to_string(),
            url_filters: std::collections::HashMap::new(),
        };
        let db = Database::new(":memory:").unwrap();
        Arc::new(AppState {
            config: RwLock::new(config),
            db,
            start_time: std::time::Instant::now(),
            config_path: "dummy_config.json".to_string(),
        })
    }

    #[tokio::test]
    async fn test_health_check() {
        let state = make_state();
        let app = app(state);
        let response = app
            .oneshot(
                axum::http::Request::builder()
                    .uri("/health")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::OK);
    }

    #[tokio::test]
    async fn test_health_check_fields() {
        let state = make_state();
        let app = app(state);
        let response = app
            .oneshot(
                axum::http::Request::builder()
                    .uri("/health")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();

        assert_eq!(response.status(), StatusCode::OK);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let json: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert_eq!(json["status"], "up");
        assert!(json["timestamp"].is_string());
        assert!(json["uptime_secs"].is_number());
        assert!(json["database"].is_string());
    }

    #[tokio::test]
    async fn test_rss_endpoint_returns_xml() {
        let state = make_state();
        let app = app(state);
        let response = app
            .oneshot(
                axum::http::Request::builder()
                    .uri("/rss")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();

        assert_eq!(response.status(), StatusCode::OK);
        let ct = response
            .headers()
            .get("content-type")
            .expect("content-type header missing")
            .to_str()
            .unwrap();
        assert!(ct.contains("rss+xml"), "Expected rss+xml, got: {}", ct);
    }

    #[tokio::test]
    async fn test_update_config_valid_and_invalid() {
        let state = make_state();
        let app = app(state.clone());

        let mut config = Config {
            server_ip: "127.0.0.1".to_string(),
            server_port: 5000,
            currency: "$".to_string(),
            refresh_interval_minutes: 15,
            log_filename: "test.log".to_string(),
            database_name: "test.db".to_string(),
            url_filters: std::collections::HashMap::new(),
        };

        // Invalid config
        config.server_port = 0;
        let response = app
            .clone()
            .oneshot(
                axum::http::Request::builder()
                    .method("POST")
                    .uri("/api/config")
                    .header("content-type", "application/json")
                    .body(Body::from(serde_json::to_string(&config).unwrap()))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::BAD_REQUEST);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let json: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert!(json["detail"].is_string());

        // Valid config
        config.server_port = 8080;
        let response = app
            .oneshot(
                axum::http::Request::builder()
                    .method("POST")
                    .uri("/api/config")
                    .header("content-type", "application/json")
                    .body(Body::from(serde_json::to_string(&config).unwrap()))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::OK);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let json: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert!(json["message"].is_string());
        assert_eq!(state.config.read().await.server_port, 8080);
    }
}
