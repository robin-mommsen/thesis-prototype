CREATE TABLE IF NOT EXISTS query_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_id VARCHAR(255),
    user_goal TEXT NOT NULL,
    factsheets_retrieved JSONB,
    factsheet_count INTEGER,
    llm_response TEXT,
    response_time_ms INTEGER,
    error_message TEXT,
    success BOOLEAN DEFAULT true,
    used_rag BOOLEAN DEFAULT true,
    prompt_sent TEXT
);

CREATE INDEX IF NOT EXISTS idx_query_logs_timestamp ON query_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_query_logs_user_id ON query_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_query_logs_used_rag ON query_logs(used_rag);
