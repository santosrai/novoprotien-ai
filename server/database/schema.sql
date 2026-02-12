-- Users table
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE, -- NULL for AI agents
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT, -- NULL for AI agents
    user_type TEXT NOT NULL DEFAULT 'human', -- 'human' | 'ai'
    role TEXT NOT NULL DEFAULT 'user', -- 'user', 'admin', 'moderator'
    agent_id TEXT, -- References agent registry (e.g., 'code-builder', 'alphafold-agent')
    model_version TEXT, -- e.g., 'anthropic/claude-3.5-sonnet'
    email_verified BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT 1,
    profile_data TEXT -- JSON string for additional profile info
);

-- User credits table
CREATE TABLE IF NOT EXISTS user_credits (
    user_id TEXT PRIMARY KEY,
    credits INTEGER DEFAULT 0,
    total_earned INTEGER DEFAULT 0,
    total_spent INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Credit transactions table
CREATE TABLE IF NOT EXISTS credit_transactions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    amount INTEGER NOT NULL, -- positive for earned, negative for spent
    transaction_type TEXT NOT NULL, -- 'earned', 'spent', 'admin_adjustment', 'purchase'
    description TEXT,
    related_job_id TEXT, -- Links to AlphaFold/RFdiffusion/ProteinMPNN job
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Usage history table
CREATE TABLE IF NOT EXISTS usage_history (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    action_type TEXT NOT NULL, -- 'alphafold', 'rfdiffusion', 'proteinmpnn', 'agent_chat', 'pipeline_execution'
    resource_consumed TEXT, -- JSON: credits, compute_time, etc.
    metadata TEXT, -- JSON: job_id, parameters, etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- User reports table
CREATE TABLE IF NOT EXISTS user_reports (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    report_type TEXT NOT NULL, -- 'bug', 'feature_request', 'abuse', 'other'
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT DEFAULT 'pending', -- 'pending', 'reviewing', 'resolved', 'dismissed'
    priority TEXT DEFAULT 'medium', -- 'low', 'medium', 'high', 'critical'
    admin_notes TEXT,
    assigned_admin_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (assigned_admin_id) REFERENCES users(id)
);

-- Email verification tokens
CREATE TABLE IF NOT EXISTS email_verification_tokens (
    token TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Password reset tokens
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    token TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    used BOOLEAN DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Refresh tokens (for JWT refresh)
CREATE TABLE IF NOT EXISTS refresh_tokens (
    token TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_credit_transactions_user_id ON credit_transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_credit_transactions_created_at ON credit_transactions(created_at);
CREATE INDEX IF NOT EXISTS idx_usage_history_user_id ON usage_history(user_id);
CREATE INDEX IF NOT EXISTS idx_usage_history_created_at ON usage_history(created_at);
CREATE INDEX IF NOT EXISTS idx_user_reports_status ON user_reports(status);
CREATE INDEX IF NOT EXISTS idx_user_reports_user_id ON user_reports(user_id);

-- User file storage metadata (replaces JSON index)
CREATE TABLE IF NOT EXISTS user_files (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    file_type TEXT NOT NULL, -- 'upload', 'rfdiffusion', 'proteinmpnn', 'alphafold'
    original_filename TEXT,
    stored_path TEXT NOT NULL, -- Relative: storage/{user_id}/uploads/pdb/{file_id}.pdb
    size INTEGER,
    metadata TEXT, -- JSON: atoms, chains, chain_residue_counts, etc.
    job_id TEXT, -- For result files (links to job)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_user_files_user_id ON user_files(user_id);
CREATE INDEX idx_user_files_type ON user_files(file_type);
CREATE INDEX idx_user_files_job_id ON user_files(job_id);

-- Chat sessions (migrate from frontend localStorage)
-- Keep for backward compatibility during migration
CREATE TABLE IF NOT EXISTS chat_sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    title TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_chat_sessions_user_id ON chat_sessions(user_id);

-- Conversations (new table, replaces chat_sessions)
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    ai_agent_id TEXT REFERENCES users(id), -- AI participant
    title TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_conversations_user_id ON conversations(user_id);
CREATE INDEX idx_conversations_ai_agent_id ON conversations(ai_agent_id);

-- Chat messages (store actual message content)
CREATE TABLE IF NOT EXISTS chat_messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL, -- Keep for backward compatibility
    conversation_id TEXT, -- New field, references conversations
    user_id TEXT NOT NULL, -- Keep for backward compatibility
    sender_id TEXT REFERENCES users(id), -- Can be human or AI user_id
    content TEXT NOT NULL,
    message_type TEXT NOT NULL DEFAULT 'user', -- 'user', 'ai', 'text', 'tool_call', 'tool_result'
    role TEXT, -- 'user', 'assistant', 'system'
    metadata TEXT, -- JSON: jobId, jobType, thinkingProcess, results, etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_chat_messages_session_id ON chat_messages(session_id);
CREATE INDEX idx_chat_messages_conversation_id ON chat_messages(conversation_id);
CREATE INDEX idx_chat_messages_user_id ON chat_messages(user_id);
CREATE INDEX idx_chat_messages_sender_id ON chat_messages(sender_id);
CREATE INDEX idx_chat_messages_created_at ON chat_messages(created_at);

-- Session-file associations (replaces session_files.json)
CREATE TABLE IF NOT EXISTS session_files (
    session_id TEXT NOT NULL,
    file_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (session_id, file_id),
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (file_id) REFERENCES user_files(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_session_files_session_id ON session_files(session_id);
CREATE INDEX idx_session_files_file_id ON session_files(file_id);

-- Pipeline storage (normalized schema)
CREATE TABLE IF NOT EXISTS pipelines (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    message_id TEXT REFERENCES chat_messages(id) ON DELETE SET NULL,
    conversation_id TEXT REFERENCES conversations(id) ON DELETE SET NULL,
    name TEXT NOT NULL DEFAULT 'Untitled Pipeline',
    description TEXT,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'running', 'completed', 'failed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_pipelines_user_id ON pipelines(user_id);
CREATE INDEX IF NOT EXISTS idx_pipelines_message_id ON pipelines(message_id);
CREATE INDEX IF NOT EXISTS idx_pipelines_conversation_id ON pipelines(conversation_id);
CREATE INDEX IF NOT EXISTS idx_pipelines_status ON pipelines(status);
CREATE INDEX IF NOT EXISTS idx_pipelines_updated_at ON pipelines(updated_at);

-- Pipeline nodes (individual node records)
CREATE TABLE IF NOT EXISTS pipeline_nodes (
    id TEXT NOT NULL,
    pipeline_id TEXT NOT NULL,
    type TEXT NOT NULL
        CHECK (type IN (
            'input_node', 'rfdiffusion_node', 'proteinmpnn_node',
            'alphafold_node', 'openfold2_node', 'message_input_node',
            'http_request_node'
        )),
    label TEXT NOT NULL,
    config TEXT NOT NULL DEFAULT '{}',         -- JSON: node-specific configuration
    inputs TEXT NOT NULL DEFAULT '{}',         -- JSON: map of input handle IDs to source node IDs
    status TEXT NOT NULL DEFAULT 'idle'
        CHECK (status IN ('idle', 'running', 'success', 'completed', 'error', 'pending')),
    result_metadata TEXT,                      -- JSON: execution results
    error TEXT,
    position_x REAL DEFAULT 0,
    position_y REAL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id, pipeline_id),
    FOREIGN KEY (pipeline_id) REFERENCES pipelines(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_pipeline_nodes_pipeline_id ON pipeline_nodes(pipeline_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_nodes_type ON pipeline_nodes(type);
CREATE INDEX IF NOT EXISTS idx_pipeline_nodes_status ON pipeline_nodes(status);

-- Pipeline edges (node-to-node connections)
CREATE TABLE IF NOT EXISTS pipeline_edges (
    id TEXT PRIMARY KEY,
    pipeline_id TEXT NOT NULL,
    source_node_id TEXT NOT NULL,
    target_node_id TEXT NOT NULL,
    source_handle TEXT DEFAULT 'source',
    target_handle TEXT DEFAULT 'target',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (pipeline_id) REFERENCES pipelines(id) ON DELETE CASCADE,
    FOREIGN KEY (source_node_id, pipeline_id) REFERENCES pipeline_nodes(id, pipeline_id) ON DELETE CASCADE,
    FOREIGN KEY (target_node_id, pipeline_id) REFERENCES pipeline_nodes(id, pipeline_id) ON DELETE CASCADE,
    UNIQUE (pipeline_id, source_node_id, target_node_id, source_handle, target_handle)
);

CREATE INDEX IF NOT EXISTS idx_pipeline_edges_pipeline_id ON pipeline_edges(pipeline_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_edges_source ON pipeline_edges(source_node_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_edges_target ON pipeline_edges(target_node_id);

-- Pipeline executions (execution sessions)
CREATE TABLE IF NOT EXISTS pipeline_executions (
    id TEXT PRIMARY KEY,
    pipeline_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'completed', 'failed', 'stopped', 'cancelled')),
    trigger_type TEXT DEFAULT 'manual'
        CHECK (trigger_type IN ('manual', 'rerun', 'single_node', 'scheduled')),
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    total_duration_ms INTEGER,
    error_summary TEXT,
    metadata TEXT,                             -- JSON: additional execution metadata
    FOREIGN KEY (pipeline_id) REFERENCES pipelines(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_pipeline_executions_pipeline_id ON pipeline_executions(pipeline_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_executions_user_id ON pipeline_executions(user_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_executions_status ON pipeline_executions(status);
CREATE INDEX IF NOT EXISTS idx_pipeline_executions_started_at ON pipeline_executions(started_at);

-- Pipeline node executions (per-node execution results)
CREATE TABLE IF NOT EXISTS pipeline_node_executions (
    id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    pipeline_id TEXT NOT NULL,
    node_label TEXT NOT NULL,
    node_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'running', 'success', 'completed', 'error', 'skipped')),
    execution_order INTEGER,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_ms INTEGER,
    error TEXT,
    input_data TEXT,                           -- JSON: config, file refs, upstream outputs
    output_data TEXT,                          -- JSON: execution result (file refs only, no raw PDB)
    request_method TEXT,
    request_url TEXT,
    request_headers TEXT,                      -- JSON
    request_body TEXT,                         -- JSON
    response_status INTEGER,
    response_status_text TEXT,
    response_headers TEXT,                     -- JSON
    response_data TEXT,                        -- JSON (file refs only, raw PDB stays on disk)
    FOREIGN KEY (execution_id) REFERENCES pipeline_executions(id) ON DELETE CASCADE,
    FOREIGN KEY (node_id, pipeline_id) REFERENCES pipeline_nodes(id, pipeline_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_pne_execution_id ON pipeline_node_executions(execution_id);
CREATE INDEX IF NOT EXISTS idx_pne_node_id ON pipeline_node_executions(node_id);
CREATE INDEX IF NOT EXISTS idx_pne_status ON pipeline_node_executions(status);
CREATE INDEX IF NOT EXISTS idx_pne_execution_order ON pipeline_node_executions(execution_id, execution_order);

-- Pipeline node files (file references per node)
CREATE TABLE IF NOT EXISTS pipeline_node_files (
    id TEXT PRIMARY KEY,
    pipeline_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    execution_id TEXT,
    node_execution_id TEXT,
    file_id TEXT REFERENCES user_files(id) ON DELETE SET NULL,
    role TEXT NOT NULL
        CHECK (role IN ('input', 'output', 'template', 'reference')),
    file_type TEXT DEFAULT 'pdb',              -- 'pdb', 'sequence', 'a3m', 'hhr', 'json'
    filename TEXT,
    file_url TEXT,
    file_path TEXT,
    metadata TEXT,                             -- JSON: atoms, chains, residues, etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (pipeline_id) REFERENCES pipelines(id) ON DELETE CASCADE,
    FOREIGN KEY (node_id, pipeline_id) REFERENCES pipeline_nodes(id, pipeline_id) ON DELETE CASCADE,
    FOREIGN KEY (execution_id) REFERENCES pipeline_executions(id) ON DELETE SET NULL,
    FOREIGN KEY (node_execution_id) REFERENCES pipeline_node_executions(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_pnf_pipeline_id ON pipeline_node_files(pipeline_id);
CREATE INDEX IF NOT EXISTS idx_pnf_node_id ON pipeline_node_files(node_id);
CREATE INDEX IF NOT EXISTS idx_pnf_execution_id ON pipeline_node_files(execution_id);
CREATE INDEX IF NOT EXISTS idx_pnf_file_id ON pipeline_node_files(file_id);
CREATE INDEX IF NOT EXISTS idx_pnf_role ON pipeline_node_files(role);

-- Typed views for querying node-specific config fields
CREATE VIEW IF NOT EXISTS v_input_nodes AS
SELECT
    pn.id, pn.pipeline_id, pn.label, pn.status,
    json_extract(pn.config, '$.filename') AS filename,
    json_extract(pn.config, '$.file_id') AS file_id,
    json_extract(pn.config, '$.atoms') AS atoms,
    json_extract(pn.config, '$.chains') AS chains,
    json_extract(pn.config, '$.total_residues') AS total_residues,
    json_extract(pn.config, '$.suggested_contigs') AS suggested_contigs,
    pn.result_metadata, pn.error, pn.position_x, pn.position_y
FROM pipeline_nodes pn WHERE pn.type = 'input_node';

CREATE VIEW IF NOT EXISTS v_rfdiffusion_nodes AS
SELECT
    pn.id, pn.pipeline_id, pn.label, pn.status,
    json_extract(pn.config, '$.design_mode') AS design_mode,
    json_extract(pn.config, '$.contigs') AS contigs,
    json_extract(pn.config, '$.hotspot_res') AS hotspot_res,
    json_extract(pn.config, '$.diffusion_steps') AS diffusion_steps,
    json_extract(pn.config, '$.num_designs') AS num_designs,
    json_extract(pn.config, '$.pdb_id') AS pdb_id,
    pn.result_metadata, pn.error, pn.position_x, pn.position_y
FROM pipeline_nodes pn WHERE pn.type = 'rfdiffusion_node';

CREATE VIEW IF NOT EXISTS v_proteinmpnn_nodes AS
SELECT
    pn.id, pn.pipeline_id, pn.label, pn.status,
    json_extract(pn.config, '$.num_sequences') AS num_sequences,
    json_extract(pn.config, '$.temperature') AS temperature,
    pn.result_metadata, pn.error, pn.position_x, pn.position_y
FROM pipeline_nodes pn WHERE pn.type = 'proteinmpnn_node';

CREATE VIEW IF NOT EXISTS v_alphafold_nodes AS
SELECT
    pn.id, pn.pipeline_id, pn.label, pn.status,
    json_extract(pn.config, '$.recycle_count') AS recycle_count,
    json_extract(pn.config, '$.num_relax') AS num_relax,
    pn.result_metadata, pn.error, pn.position_x, pn.position_y
FROM pipeline_nodes pn WHERE pn.type = 'alphafold_node';

CREATE VIEW IF NOT EXISTS v_openfold2_nodes AS
SELECT
    pn.id, pn.pipeline_id, pn.label, pn.status,
    json_extract(pn.config, '$.sequence') AS sequence,
    json_extract(pn.config, '$.relax_prediction') AS relax_prediction,
    pn.result_metadata, pn.error, pn.position_x, pn.position_y
FROM pipeline_nodes pn WHERE pn.type = 'openfold2_node';

-- Session state (canvas/viewer state, model settings)
CREATE TABLE IF NOT EXISTS session_state (
    session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    visualization_code TEXT,
    viewer_visible BOOLEAN DEFAULT 0,
    model_settings TEXT, -- JSON: {selectedAgentId, selectedModel}
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_session_state_user_id ON session_state(user_id);
CREATE INDEX idx_session_state_updated_at ON session_state(updated_at);

-- Three D Canvases (message-scoped visualization code)
CREATE TABLE IF NOT EXISTS three_d_canvases (
    id TEXT PRIMARY KEY,
    message_id TEXT REFERENCES chat_messages(id),
    conversation_id TEXT REFERENCES conversations(id),
    scene_data TEXT NOT NULL, -- JSON: {molstar_code, camera_position, objects, etc.}
    preview_url TEXT,
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_three_d_canvases_message_id ON three_d_canvases(message_id);
CREATE INDEX idx_three_d_canvases_conversation_id ON three_d_canvases(conversation_id);

-- Attachments (message-scoped file attachments)
CREATE TABLE IF NOT EXISTS attachments (
    id TEXT PRIMARY KEY,
    message_id TEXT REFERENCES chat_messages(id),
    file_id TEXT REFERENCES user_files(id),
    file_name TEXT,
    file_type TEXT, -- MIME type
    file_size_kb INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_attachments_message_id ON attachments(message_id);
CREATE INDEX idx_attachments_file_id ON attachments(file_id);

-- Admin audit log table
CREATE TABLE IF NOT EXISTS admin_audit_log (
    id TEXT PRIMARY KEY,
    admin_id TEXT NOT NULL,
    action_type TEXT NOT NULL, -- 'view_user', 'export_data', 'revoke_token', etc.
    target_type TEXT, -- 'user', 'message', 'token'
    target_id TEXT,
    details TEXT, -- JSON: request params, filters, etc.
    ip_address TEXT,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (admin_id) REFERENCES users(id)
);

CREATE INDEX idx_admin_audit_admin_id ON admin_audit_log(admin_id);
CREATE INDEX idx_admin_audit_action_type ON admin_audit_log(action_type);
CREATE INDEX idx_admin_audit_created_at ON admin_audit_log(created_at);

-- Admin preferences table
CREATE TABLE IF NOT EXISTS admin_preferences (
    admin_id TEXT PRIMARY KEY,
    privacy_mode BOOLEAN DEFAULT 0,
    masked_fields TEXT, -- JSON array of field names to mask
    default_page_size INTEGER DEFAULT 25,
    preferred_view TEXT, -- 'table'|'thread'|'both'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (admin_id) REFERENCES users(id)
);

-- AlphaFold jobs table (for long-running job persistence)
CREATE TABLE IF NOT EXISTS alphafold_jobs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    session_id TEXT,
    sequence TEXT NOT NULL,
    sequence_length INTEGER NOT NULL,
    parameters TEXT, -- JSON parameters
    status TEXT NOT NULL DEFAULT 'queued', -- 'queued'|'running'|'completed'|'error'|'cancelled'
    nvidia_req_id TEXT, -- NVIDIA API request ID for recovery
    result_filepath TEXT, -- Path to result PDB file
    error_message TEXT, -- Error details if failed
    progress REAL DEFAULT 0.0, -- Progress percentage (0-100)
    progress_message TEXT, -- Current status message
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE SET NULL
);

CREATE INDEX idx_alphafold_jobs_user_id ON alphafold_jobs(user_id);
CREATE INDEX idx_alphafold_jobs_status ON alphafold_jobs(status);
CREATE INDEX idx_alphafold_jobs_created_at ON alphafold_jobs(created_at);
CREATE INDEX idx_alphafold_jobs_nvidia_req_id ON alphafold_jobs(nvidia_req_id);

