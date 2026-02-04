-- Pipeline Canvas: Standalone migrations for pipelines and pipeline_executions
-- Run this SQL against your database to create the required tables.
-- No foreign keys to chat_messages/conversations - use plain TEXT for message_id, conversation_id.

CREATE TABLE IF NOT EXISTS pipelines (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    message_id TEXT,
    conversation_id TEXT,
    name TEXT,
    description TEXT,
    pipeline_json TEXT NOT NULL,
    status TEXT DEFAULT 'draft',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pipelines_user_id ON pipelines(user_id);
CREATE INDEX IF NOT EXISTS idx_pipelines_message_id ON pipelines(message_id);
CREATE INDEX IF NOT EXISTS idx_pipelines_conversation_id ON pipelines(conversation_id);
CREATE INDEX IF NOT EXISTS idx_pipelines_status ON pipelines(status);

CREATE TABLE IF NOT EXISTS pipeline_executions (
    id TEXT PRIMARY KEY,
    pipeline_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    status TEXT DEFAULT 'running',
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    execution_log TEXT
);

CREATE INDEX IF NOT EXISTS idx_pipeline_executions_user_id ON pipeline_executions(user_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_executions_pipeline_id ON pipeline_executions(pipeline_id);
