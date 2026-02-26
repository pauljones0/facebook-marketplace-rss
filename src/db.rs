use anyhow::Result;
use chrono::{DateTime, Duration, Utc};
use r2d2::Pool;
use r2d2_sqlite::SqliteConnectionManager;

pub struct Database {
    pool: Pool<SqliteConnectionManager>,
}

#[derive(Debug, PartialEq, Clone)]
pub struct AdEntry {
    pub ad_id: String,
    pub title: String,
    pub price: String,
    pub url: String,
    pub first_seen: DateTime<Utc>,
    pub last_checked: DateTime<Utc>,
}

impl Database {
    pub fn new(path: &str) -> anyhow::Result<Self> {
        let manager = SqliteConnectionManager::file(path);
        let pool = Pool::new(manager).map_err(|e| anyhow::anyhow!("Pool error: {}", e))?;

        let conn = pool
            .get()
            .map_err(|e| anyhow::anyhow!("Pool connection error: {}", e))?;
        conn.execute(
            "CREATE TABLE IF NOT EXISTS ad_changes (
                url TEXT,
                ad_id TEXT PRIMARY KEY,
                title TEXT,
                price TEXT,
                first_seen TEXT,
                last_checked TEXT
            )",
            [],
        )?;
        Ok(Database { pool })
    }

    pub fn insert_or_update_ad(&self, entry: &AdEntry) -> Result<bool> {
        let conn = self
            .pool
            .get()
            .map_err(|e| anyhow::anyhow!("Pool connection error: {}", e))?;
        let mut stmt = conn.prepare("SELECT ad_id FROM ad_changes WHERE ad_id = ?")?;
        let exists = stmt.exists([&entry.ad_id])?;

        let now_iso = entry.last_checked.to_rfc3339();

        if !exists {
            conn.execute(
                "INSERT INTO ad_changes (url, ad_id, title, price, first_seen, last_checked) VALUES (?, ?, ?, ?, ?, ?)",
                (&entry.url, &entry.ad_id, &entry.title, &entry.price, &entry.first_seen.to_rfc3339(), &now_iso),
            )?;
            Ok(true)
        } else {
            conn.execute(
                "UPDATE ad_changes SET last_checked = ?, title = ?, price = ? WHERE ad_id = ?",
                (&now_iso, &entry.title, &entry.price, &entry.ad_id),
            )?;
            Ok(false)
        }
    }

    pub fn prune_old_ads(&self, days_to_keep: i64) -> Result<usize> {
        let conn = self
            .pool
            .get()
            .map_err(|e| anyhow::anyhow!("Pool connection error: {}", e))?;
        let cutoff = Utc::now() - Duration::days(days_to_keep);
        let cutoff_iso = cutoff.to_rfc3339();
        let deleted = conn.execute(
            "DELETE FROM ad_changes WHERE last_checked < ?",
            [&cutoff_iso],
        )?;
        Ok(deleted)
    }

    pub fn get_recent_ads(&self, days: i64) -> Result<Vec<AdEntry>> {
        let conn = self
            .pool
            .get()
            .map_err(|e| anyhow::anyhow!("Pool connection error: {}", e))?;
        let cutoff = Utc::now() - Duration::days(days);
        let cutoff_iso = cutoff.to_rfc3339();
        let mut stmt = conn.prepare(
            "SELECT ad_id, title, price, url, first_seen, last_checked FROM ad_changes WHERE last_checked >= ? ORDER BY last_checked DESC"
        )?;

        let entries = stmt
            .query_map([&cutoff_iso], |row: &rusqlite::Row| {
                Ok(AdEntry {
                    ad_id: row.get::<usize, String>(0)?,
                    title: row.get::<usize, String>(1)?,
                    price: row.get::<usize, String>(2)?,
                    url: row.get::<usize, String>(3)?,
                    first_seen: DateTime::parse_from_rfc3339(&row.get::<usize, String>(4)?)
                        .map(|dt| dt.with_timezone(&Utc))
                        .unwrap_or_else(|_| Utc::now()),
                    last_checked: DateTime::parse_from_rfc3339(&row.get::<usize, String>(5)?)
                        .map(|dt| dt.with_timezone(&Utc))
                        .unwrap_or_else(|_| Utc::now()),
                })
            })?
            .collect::<Result<Vec<_>, _>>()?;

        Ok(entries)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_db_init_and_insert() {
        let db = Database::new(":memory:").unwrap();
        let now = Utc::now();
        let entry = AdEntry {
            ad_id: "test_id".to_string(),
            title: "Test Ad".to_string(),
            price: "$100".to_string(),
            url: "https://example.com/ad1".to_string(),
            first_seen: now,
            last_checked: now,
        };

        let is_new = db.insert_or_update_ad(&entry).unwrap();
        assert!(is_new);

        let is_new_again = db.insert_or_update_ad(&entry).unwrap();
        assert!(!is_new_again);
    }

    #[test]
    fn test_db_pruning() {
        let db = Database::new(":memory:").unwrap();
        let old_date = Utc::now() - Duration::days(20);
        let entry = AdEntry {
            ad_id: "old_ad".to_string(),
            title: "Old Ad".to_string(),
            price: "$10".to_string(),
            url: "https://example.com/old".to_string(),
            first_seen: old_date,
            last_checked: old_date,
        };

        db.insert_or_update_ad(&entry).unwrap();
        let pruned = db.prune_old_ads(14).unwrap();
        assert_eq!(pruned, 1);
    }

    #[test]
    fn test_get_recent_ads() {
        let db = Database::new(":memory:").unwrap();
        let now = Utc::now();
        let entry = AdEntry {
            ad_id: "recent".to_string(),
            title: "Recent Ad".to_string(),
            price: "$100".to_string(),
            url: "https://example.com/recent".to_string(),
            first_seen: now,
            last_checked: now,
        };

        db.insert_or_update_ad(&entry).unwrap();
        let recent = db.get_recent_ads(1).unwrap();
        assert_eq!(recent.len(), 1);
        assert_eq!(recent[0].ad_id, "recent");
    }
}
