-- Durable CV-analysis queue (click stores a ticket, a worker runs matching).
CREATE TABLE IF NOT EXISTS analysis_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    job_provider TEXT NOT NULL,
    analysis_depth TEXT NOT NULL DEFAULT 'standard',
    matching_pool INTEGER NOT NULL,
    matching_top INTEGER NOT NULL,
    cv_fingerprint TEXT NOT NULL DEFAULT '',
    cv_text TEXT,
    extraction_method TEXT NOT NULL DEFAULT 'native',
    pdf_blob BLOB,
    user_profile_json TEXT NOT NULL,
    trigger_source TEXT NOT NULL DEFAULT 'ui',
    progress_percent INTEGER NOT NULL DEFAULT 0,
    progress_label TEXT NOT NULL DEFAULT '',
    error_message TEXT,
    analysis_id INTEGER,
    notices_json TEXT
);

CREATE INDEX IF NOT EXISTS analysis_jobs_status_idx
    ON analysis_jobs (status, id);

CREATE INDEX IF NOT EXISTS analysis_jobs_user_idx
    ON analysis_jobs (user_id, created_at);
