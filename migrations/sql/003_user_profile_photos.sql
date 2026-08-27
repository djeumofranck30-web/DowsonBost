-- One square profile photo per candidate.
CREATE TABLE IF NOT EXISTS user_profile_photos (
    user_id INTEGER PRIMARY KEY,
    mime_type TEXT NOT NULL,
    image_data BLOB NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
