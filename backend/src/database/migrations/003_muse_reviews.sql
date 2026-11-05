CREATE TABLE IF NOT EXISTS anomaly_reviews (
  analysis_id TEXT NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
  anomaly_id TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('processing','completed','failed')),
  request_id TEXT NOT NULL,
  lease_until REAL NOT NULL,
  result TEXT,
  error TEXT,
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  PRIMARY KEY (analysis_id, anomaly_id)
);
PRAGMA user_version = 3;
