-- Migration: Make messages.business_id nullable
-- Date: 2025-08-24
-- Description: Recreate messages table with business_id allowing NULL (SQLite does not support altering nullability directly)

PRAGMA foreign_keys=off;

-- Create new table with desired schema
CREATE TABLE IF NOT EXISTS messages_tmp (
  id INTEGER PRIMARY KEY,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
  updated_at DATETIME,
  session_id VARCHAR(50) NOT NULL,
  business_id INTEGER,
  sender_type VARCHAR(20) NOT NULL,
  content TEXT NOT NULL,
  message_type VARCHAR(20) DEFAULT 'text',
  intent_detected VARCHAR(50),
  ai_model_used VARCHAR(50),
  response_time_ms INTEGER,
  extra_data JSON,
  FOREIGN KEY(business_id) REFERENCES businesses(id) ON DELETE CASCADE
);

-- Copy data from old table
INSERT INTO messages_tmp (
  id, created_at, updated_at, session_id, business_id, sender_type, content,
  message_type, intent_detected, ai_model_used, response_time_ms, extra_data
)
SELECT 
  id, created_at, updated_at, session_id, business_id, sender_type, content,
  message_type, intent_detected, ai_model_used, response_time_ms, extra_data
FROM messages;

-- Replace old table with new
DROP TABLE messages;
ALTER TABLE messages_tmp RENAME TO messages;

-- Recreate indexes
CREATE INDEX IF NOT EXISTS ix_messages_session_id ON messages (session_id);
CREATE INDEX IF NOT EXISTS ix_messages_business_id ON messages (business_id);

PRAGMA foreign_keys=on;
