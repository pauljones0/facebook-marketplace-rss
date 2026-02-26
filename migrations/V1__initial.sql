CREATE TABLE IF NOT EXISTS ad_changes (
    url TEXT,
    ad_id TEXT PRIMARY KEY,
    title TEXT,
    price TEXT,
    first_seen TEXT,
    last_checked TEXT
);
CREATE INDEX IF NOT EXISTS idx_ad_id ON ad_changes (ad_id);
CREATE INDEX IF NOT EXISTS idx_last_checked ON ad_changes (last_checked);
