#!/usr/bin/env python3
"""
Migration script to migrate from session-scoped to message-scoped architecture.

This script:
1. Extends users table with user_type, agent_id, model_version
2. Creates AI agent users
3. Creates conversations table and migrates data from chat_sessions
4. Updates chat_messages with sender_id and conversation_id
5. Creates three_d_canvases table and migrates visualization_code
6. Creates attachments table
7. Updates pipelines table with message_id and conversation_id
"""

import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional
import sys
import os
from datetime import datetime

# Add server directory to path
migration_file_dir = Path(__file__).parent  # server/database/migrations/
server_dir = migration_file_dir.parent.parent  # server/
db_file_path = migration_file_dir.parent / "db.py"  # server/database/db.py

# Set up path for imports
sys.path.insert(0, str(server_dir))

# Mock infrastructure.config before importing db
class MockConfig:
    @staticmethod
    def get_server_dir():
        return server_dir

# Create mock modules
import types
infra_module = types.ModuleType('infrastructure')
config_module = types.ModuleType('infrastructure.config')
config_module.get_server_dir = MockConfig.get_server_dir
infra_module.config = config_module
sys.modules['infrastructure'] = infra_module
sys.modules['infrastructure.config'] = config_module

# Import db module
import importlib.util
with open(db_file_path, 'r') as f:
    db_code = f.read()

db_code = db_code.replace(
    'from ..infrastructure.config import get_server_dir',
    'from infrastructure.config import get_server_dir'
)

db_spec = importlib.util.spec_from_file_location("db_module", str(db_file_path))
db_module = importlib.util.module_from_spec(db_spec)
exec(compile(db_code, str(db_file_path), 'exec'), db_module.__dict__)
get_db = db_module.get_db


def add_columns_to_users():
    """Add user_type, agent_id, model_version columns to users table."""
    print("Adding columns to users table...")
    with get_db() as conn:
        try:
            conn.execute("ALTER TABLE users ADD COLUMN user_type TEXT DEFAULT 'human'")
            print("  ✓ Added user_type column")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower():
                print("  ✓ user_type column already exists")
            else:
                raise
        
        try:
            conn.execute("ALTER TABLE users ADD COLUMN agent_id TEXT")
            print("  ✓ Added agent_id column")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower():
                print("  ✓ agent_id column already exists")
            else:
                raise
        
        try:
            conn.execute("ALTER TABLE users ADD COLUMN model_version TEXT")
            print("  ✓ Added model_version column")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower():
                print("  ✓ model_version column already exists")
            else:
                raise


def create_ai_agents():
    """Create AI agent users in the database."""
    print("\nCreating AI agent users...")
    
    ai_agents = [
        ('ai-code-builder', 'Code Builder Agent', 'code-builder', 'anthropic/claude-3.5-sonnet'),
        ('ai-mvs-builder', 'MVS Builder Agent', 'mvs-builder', 'anthropic/claude-3.5-sonnet'),
        ('ai-bio-chat', 'Bio Chat Agent', 'bio-chat', 'anthropic/claude-3.5-sonnet'),
        ('ai-alphafold', 'AlphaFold Agent', 'alphafold-agent', 'anthropic/claude-3.5-sonnet'),
        ('ai-rfdiffusion', 'RFdiffusion Agent', 'rfdiffusion-agent', 'anthropic/claude-3.5-sonnet'),
        ('ai-proteinmpnn', 'ProteinMPNN Agent', 'proteinmpnn-agent', 'anthropic/claude-3.5-sonnet'),
        ('ai-pipeline', 'Pipeline Agent', 'pipeline-agent', 'anthropic/claude-3.5-sonnet'),
    ]
    
    with get_db() as conn:
        for agent_id, username, agent_registry_id, model_version in ai_agents:
            # Check if agent already exists
            existing = conn.execute(
                "SELECT id FROM users WHERE id = ?",
                (agent_id,)
            ).fetchone()
            
            if existing:
                print(f"  ✓ AI agent {agent_id} already exists")
                # Update existing agent
                conn.execute(
                    """UPDATE users 
                       SET user_type = 'ai', agent_id = ?, model_version = ?, is_active = 1
                       WHERE id = ?""",
                    (agent_registry_id, model_version, agent_id)
                )
            else:
                # Create new agent
                # Use placeholder email and password_hash for AI agents
                # (Some databases may have NOT NULL constraints from older schemas)
                placeholder_email = f"{agent_id}@ai-agent.local"
                placeholder_password_hash = "ai-agent-no-password"  # Placeholder, not used for authentication
                conn.execute(
                    """INSERT INTO users (id, email, username, password_hash, user_type, agent_id, model_version, is_active, created_at)
                       VALUES (?, ?, ?, ?, 'ai', ?, ?, 1, ?)""",
                    (agent_id, placeholder_email, username, placeholder_password_hash, agent_registry_id, model_version, datetime.utcnow())
                )
                print(f"  ✓ Created AI agent: {agent_id}")


def create_conversations_table():
    """Create conversations table and migrate data from chat_sessions."""
    print("\nCreating conversations table...")
    with get_db() as conn:
        # Create table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id),
                ai_agent_id TEXT REFERENCES users(id),
                title TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        # Create indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_ai_agent_id ON conversations(ai_agent_id)")
        
        print("  ✓ Created conversations table")
        
        # Migrate data from chat_sessions
        print("  Migrating data from chat_sessions to conversations...")
        sessions = conn.execute("SELECT * FROM chat_sessions").fetchall()
        
        migrated = 0
        for session in sessions:
            # Check if conversation already exists
            existing = conn.execute(
                "SELECT id FROM conversations WHERE id = ?",
                (session['id'],)
            ).fetchone()
            
            if not existing:
                # SQLite Row objects use dictionary-style access, not .get()
                title = session['title'] if 'title' in session.keys() else None
                created_at = session['created_at'] if 'created_at' in session.keys() else None
                updated_at = session['updated_at'] if 'updated_at' in session.keys() else None
                conn.execute(
                    """INSERT INTO conversations (id, user_id, title, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (session['id'], session['user_id'], title, created_at, updated_at)
                )
                migrated += 1
        
        print(f"  ✓ Migrated {migrated} sessions to conversations")


def update_messages_table():
    """Add sender_id and conversation_id to chat_messages."""
    print("\nUpdating chat_messages table...")
    with get_db() as conn:
        # Add sender_id column
        try:
            conn.execute("ALTER TABLE chat_messages ADD COLUMN sender_id TEXT REFERENCES users(id)")
            print("  ✓ Added sender_id column")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower():
                print("  ✓ sender_id column already exists")
            else:
                raise
        
        # Add conversation_id column
        try:
            conn.execute("ALTER TABLE chat_messages ADD COLUMN conversation_id TEXT REFERENCES conversations(id)")
            print("  ✓ Added conversation_id column")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_conversation_id ON chat_messages(conversation_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_sender_id ON chat_messages(sender_id)")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower():
                print("  ✓ conversation_id column already exists")
            else:
                raise
        
        # Update existing messages: set sender_id = user_id, conversation_id = session_id
        print("  Updating existing messages...")
        messages = conn.execute("SELECT id, session_id, user_id, message_type FROM chat_messages").fetchall()
        
        updated = 0
        for msg in messages:
            updates = []
            params = []
            
            # SQLite Row objects use dictionary-style access
            sender_id = msg['sender_id'] if 'sender_id' in msg.keys() else None
            conversation_id = msg['conversation_id'] if 'conversation_id' in msg.keys() else None
            
            # Set sender_id if not set
            if not sender_id:
                updates.append("sender_id = ?")
                params.append(msg['user_id'])
            
            # Set conversation_id if not set
            if not conversation_id and msg['session_id']:
                updates.append("conversation_id = ?")
                params.append(msg['session_id'])
            
            if updates:
                params.append(msg['id'])
                conn.execute(
                    f"UPDATE chat_messages SET {', '.join(updates)} WHERE id = ?",
                    params
                )
                updated += 1
        
        print(f"  ✓ Updated {updated} messages")


def create_three_d_canvases_table():
    """Create three_d_canvases table and migrate visualization_code."""
    print("\nCreating three_d_canvases table...")
    with get_db() as conn:
        # Create table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS three_d_canvases (
                id TEXT PRIMARY KEY,
                message_id TEXT REFERENCES chat_messages(id),
                conversation_id TEXT REFERENCES conversations(id),
                scene_data TEXT NOT NULL,
                preview_url TEXT,
                version INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_three_d_canvases_message_id ON three_d_canvases(message_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_three_d_canvases_conversation_id ON three_d_canvases(conversation_id)")
        
        print("  ✓ Created three_d_canvases table")
        
        # Migrate visualization_code from session_state (if table exists)
        print("  Migrating visualization_code from session_state...")
        try:
            # Check if session_state table exists
            conn.execute("SELECT 1 FROM session_state LIMIT 1").fetchone()
            states = conn.execute(
                "SELECT session_id, visualization_code, updated_at FROM session_state WHERE visualization_code IS NOT NULL AND visualization_code != ''"
            ).fetchall()
        except sqlite3.OperationalError:
            print("  ℹ session_state table does not exist, skipping visualization code migration")
            states = []
        
        migrated = 0
        for state in states:
            session_id = state['session_id']
            visualization_code = state['visualization_code']
            
            # Find the last AI message in this session/conversation
            last_ai_message = conn.execute(
                """SELECT id FROM chat_messages 
                   WHERE (session_id = ? OR conversation_id = ?) 
                   AND message_type = 'ai'
                   ORDER BY created_at DESC LIMIT 1""",
                (session_id, session_id)
            ).fetchone()
            
            if last_ai_message:
                # Check if canvas already exists for this message
                existing = conn.execute(
                    "SELECT id FROM three_d_canvases WHERE message_id = ?",
                    (last_ai_message['id'],)
                ).fetchone()
                
                if not existing:
                    import uuid
                    canvas_id = str(uuid.uuid4())
                    scene_data = json.dumps({
                        'molstar_code': visualization_code,
                        'migrated_from_session_state': True
                    })
                    
                    updated_at = state['updated_at'] if 'updated_at' in state.keys() else None
                    conn.execute(
                        """INSERT INTO three_d_canvases 
                           (id, message_id, conversation_id, scene_data, updated_at)
                           VALUES (?, ?, ?, ?, ?)""",
                        (canvas_id, last_ai_message['id'], session_id, scene_data, updated_at)
                    )
                    migrated += 1
        
        print(f"  ✓ Migrated {migrated} visualization codes to three_d_canvases")


def create_attachments_table():
    """Create attachments table."""
    print("\nCreating attachments table...")
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS attachments (
                id TEXT PRIMARY KEY,
                message_id TEXT REFERENCES chat_messages(id),
                file_id TEXT REFERENCES user_files(id),
                file_name TEXT,
                file_type TEXT,
                file_size_kb INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.execute("CREATE INDEX IF NOT EXISTS idx_attachments_message_id ON attachments(message_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_attachments_file_id ON attachments(file_id)")
        
        print("  ✓ Created attachments table")


def update_pipelines_table():
    """Add message_id and conversation_id to pipelines table."""
    print("\nUpdating pipelines table...")
    with get_db() as conn:
        # Add message_id column
        try:
            conn.execute("ALTER TABLE pipelines ADD COLUMN message_id TEXT REFERENCES chat_messages(id)")
            print("  ✓ Added message_id column")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower():
                print("  ✓ message_id column already exists")
            else:
                raise
        
        # Add conversation_id column
        try:
            conn.execute("ALTER TABLE pipelines ADD COLUMN conversation_id TEXT REFERENCES conversations(id)")
            print("  ✓ Added conversation_id column")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_pipelines_message_id ON pipelines(message_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_pipelines_conversation_id ON pipelines(conversation_id)")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower():
                print("  ✓ conversation_id column already exists")
            else:
                raise


def main():
    """Run all migration steps."""
    print("=" * 60)
    print("Message-Scoped Architecture Migration")
    print("=" * 60)
    
    try:
        add_columns_to_users()
        create_ai_agents()
        create_conversations_table()
        update_messages_table()
        create_three_d_canvases_table()
        create_attachments_table()
        update_pipelines_table()
        
        print("\n" + "=" * 60)
        print("✓ Migration completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
