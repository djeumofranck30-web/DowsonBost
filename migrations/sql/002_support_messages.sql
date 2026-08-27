-- Private 1:1 candidate ↔ admin support threads.
CREATE TABLE IF NOT EXISTS support_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    sender_role TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL,
    read_at TEXT,
    admin_id INTEGER,
    admin_email TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS support_messages_user_created_idx
    ON support_messages (user_id, created_at ASC, id ASC);

CREATE INDEX IF NOT EXISTS support_messages_unread_idx
    ON support_messages (user_id, sender_role, read_at);
