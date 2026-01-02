Conversation (conversations) [Chat Session]
│
├── Basic Info
│   ├── id (UUID/TEXT)
│   ├── user_id (FK → users.id) - Human owner
│   ├── ai_agent_id (FK → users.id) - AI participant (optional)
│   ├── title
│   ├── created_at
│   └── updated_at
│
├── Messages (messages) [One-to-Many]
│   │
│   ├── Message 1 (User Message)
│   │   ├── id
│   │   ├── conversation_id (FK)
│   │   ├── sender_id (FK → users.id) - Human user
│   │   ├── content ("Show me protein 1ABC")
│   │   ├── message_type ('text' | 'tool_call' | 'tool_result')
│   │   ├── role ('user' | 'assistant' | 'system')
│   │   ├── metadata (JSON)
│   │   │   ├── jobId (optional)
│   │   │   ├── jobType (optional)
│   │   │   ├── thinkingProcess (optional)
│   │   │   └── error (optional)
│   │   ├── created_at
│   │   │
│   │   └── Attachments (attachments) [One-to-Many]
│   │       ├── Attachment 1
│   │       │   ├── id
│   │       │   ├── message_id (FK)
│   │       │   ├── file_id (FK → user_files.id)
│   │       │   ├── file_name
│   │       │   ├── file_type (MIME type)
│   │       │   ├── file_size_kb
│   │       │   └── created_at
│   │       │
│   │       └── Attachment N
│   │           └── ... (same structure)
│   │
│   ├── Message 2 (AI Response with 3D Canvas)
│   │   ├── id
│   │   ├── conversation_id (FK)
│   │   ├── sender_id (FK → users.id) - AI agent (e.g., 'ai-code-builder')
│   │   ├── content ("Here's the 3D visualization of 1ABC")
│   │   ├── message_type ('tool_result')
│   │   ├── role ('assistant')
│   │   ├── metadata (JSON)
│   │   ├── created_at
│   │   │
│   │   ├── Three D Canvas (three_d_canvases) [One-to-One]
│   │   │   ├── id
│   │   │   ├── message_id (FK) - Links to this message
│   │   │   ├── conversation_id (FK) - For gallery view
│   │   │   ├── scene_data (JSON/TEXT)
│   │   │   │   ├── molstar_code (JavaScript code)
│   │   │   │   ├── camera_position
│   │   │   │   ├── objects (3D objects array)
│   │   │   │   ├── representations
│   │   │   │   └── annotations
│   │   │   ├── preview_url (thumbnail/screenshot)
│   │   │   ├── version
│   │   │   ├── created_at
│   │   │   └── updated_at
│   │   │
│   │   └── Attachments (attachments) [One-to-Many]
│   │       └── ... (PDB files, result files, etc.)
│   │
│   ├── Message 3 (AI Response with Pipeline)
│   │   ├── id
│   │   ├── conversation_id (FK)
│   │   ├── sender_id (FK → users.id) - AI agent (e.g., 'ai-pipeline-agent')
│   │   ├── content ("I've created a protein design pipeline for you")
│   │   ├── message_type ('tool_result')
│   │   ├── role ('assistant')
│   │   ├── metadata (JSON)
│   │   ├── created_at
│   │   │
│   │   └── Pipeline (pipelines) [One-to-One]
│   │       ├── id
│   │       ├── message_id (FK) - Links to this message
│   │       ├── conversation_id (FK) - For gallery view
│   │       ├── user_id (FK)
│   │       ├── name ("Binder Design Pipeline")
│   │       ├── description
│   │       ├── workflow_definition (JSON)
│   │       │   ├── nodes (array)
│   │       │   │   ├── Node 1 (input_node)
│   │       │   │   │   ├── id
│   │       │   │   │   ├── type
│   │       │   │   │   ├── label
│   │       │   │   │   └── config
│   │       │   │   ├── Node 2 (rfdiffusion_node)
│   │       │   │   │   └── ...
│   │       │   │   └── Node N
│   │       │   ├── edges (array)
│   │       │   │   ├── {source: "node1", target: "node2"}
│   │       │   │   └── ...
│   │       │   └── config
│   │       ├── status ('draft' | 'running' | 'completed' | 'failed')
│   │       ├── execution_log (JSON array)
│   │       │   ├── Execution Entry 1
│   │       │   │   ├── node_id
│   │       │   │   ├── status
│   │       │   │   ├── result
│   │       │   │   └── timestamp
│   │       │   └── Execution Entry N
│   │       ├── created_at
│   │       └── updated_at
│   │
│   ├── Message 4 (AI Response with Multiple Tools)
│   │   ├── id
│   │   ├── conversation_id (FK)
│   │   ├── sender_id (FK → users.id) - AI agent
│   │   ├── content ("Here's the structure and design pipeline")
│   │   ├── message_type ('tool_result')
│   │   ├── role ('assistant')
│   │   ├── metadata (JSON)
│   │   ├── created_at
│   │   │
│   │   ├── Three D Canvas (three_d_canvases) [One-to-One]
│   │   │   └── ... (3D visualization)
│   │   │
│   │   ├── Pipeline (pipelines) [One-to-One]
│   │   │   └── ... (workflow definition)
│   │   │
│   │   └── Attachments (attachments) [One-to-Many]
│   │       └── ... (result files)
│   │
│   └── Message N
│       └── ... (same structure)
│
├── Session State (session_state) [One-to-One, Backward Compatible]
│   ├── conversation_id (FK, PRIMARY KEY)
│   ├── user_id (FK)
│   ├── viewer_visible (BOOLEAN) - Global viewer toggle
│   ├── model_settings (JSON)
│   │   ├── selectedAgentId
│   │   └── selectedModel
│   └── updated_at
│
└── Associated Files (session_files) [Many-to-Many via junction table]
    ├── File Association 1
    │   ├── conversation_id (FK) - Renamed from session_id
    │   ├── file_id (FK → user_files.id)
    │   ├── user_id (FK)
    │   └── created_at
    │
    └── File Association N
        └── ... (links to user_files table)