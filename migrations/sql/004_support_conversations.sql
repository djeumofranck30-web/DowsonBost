-- Multiple private support threads per candidate.
CREATE TABLE IF NOT EXISTS support_conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT 'user',
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS support_conversations_user_idx
    ON support_conversations (user_id, created_at DESC, id DESC);

-- Existing installs: ALTER TABLE support_messages ADD COLUMN conversation_id INTEGER;
CREATE INDEX IF NOT EXISTS support_messages_conversation_idx
    ON support_messages (conversation_id, created_at ASC, id ASC);
