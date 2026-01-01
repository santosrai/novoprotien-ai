#!/usr/bin/env python3
"""Test script for user isolation implementation."""

import sys
import json
from pathlib import Path

# Add server to path
server_dir = Path(__file__).parent / "server"
sys.path.insert(0, str(server_dir))

# Mock infrastructure.config before importing
class MockConfig:
    @staticmethod
    def get_server_dir():
        return server_dir

import types
infra_module = types.ModuleType('infrastructure')
config_module = types.ModuleType('infrastructure.config')
config_module.get_server_dir = MockConfig.get_server_dir
infra_module.config = config_module
sys.modules['infrastructure'] = infra_module
sys.modules['infrastructure.config'] = config_module

from database.db import get_db
from domain.storage.pdb_storage import save_uploaded_pdb, get_uploaded_pdb, list_uploaded_pdbs
from domain.storage.session_tracker import create_chat_session, get_user_sessions, associate_file_with_session, get_session_files
from domain.storage.file_access import verify_file_ownership, list_user_files

def test_database_tables():
    """Test that all new tables exist."""
    print("=" * 60)
    print("Test 1: Database Tables")
    print("=" * 60)
    
    with get_db() as conn:
        tables = [
            "user_files",
            "chat_sessions", 
            "session_files",
            "pipelines",
            "pipeline_executions"
        ]
        
        for table in tables:
            result = conn.execute(
                f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'"
            ).fetchone()
            if result:
                print(f"✓ Table '{table}' exists")
            else:
                print(f"✗ Table '{table}' NOT found")
                return False
    
    print("✓ All tables exist\n")
    return True

def test_file_storage():
    """Test user-scoped file storage."""
    print("=" * 60)
    print("Test 2: File Storage (User-Scoped)")
    print("=" * 60)
    
    test_user_id = "test_user_123"
    test_content = b"ATOM      1  N   ALA A   1      20.154  16.967  25.468  1.00 30.00           N\n"
    test_filename = "test.pdb"
    
    try:
        # Test save
        metadata = save_uploaded_pdb(test_filename, test_content, test_user_id)
        print(f"✓ File saved: {metadata['file_id']}")
        
        # Test get with ownership
        retrieved = get_uploaded_pdb(metadata['file_id'], test_user_id)
        if retrieved:
            print(f"✓ File retrieved with ownership check")
        else:
            print(f"✗ File retrieval failed")
            return False
        
        # Test get without ownership (should fail)
        wrong_user = get_uploaded_pdb(metadata['file_id'], "wrong_user")
        if wrong_user is None:
            print(f"✓ Ownership verification works (wrong user denied)")
        else:
            print(f"✗ Ownership check failed (wrong user got file)")
            return False
        
        # Test list
        files = list_uploaded_pdbs(test_user_id)
        if len(files) > 0:
            print(f"✓ List files works: {len(files)} file(s)")
        else:
            print(f"✗ List files returned empty")
            return False
        
        print("✓ File storage tests passed\n")
        return True
    except Exception as e:
        print(f"✗ File storage test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_session_tracking():
    """Test database-backed session tracking."""
    print("=" * 60)
    print("Test 3: Session Tracking (Database-Backed)")
    print("=" * 60)
    
    test_user_id = "test_user_123"
    
    try:
        # Test create session
        session_id = create_chat_session(test_user_id, "Test Session")
        print(f"✓ Session created: {session_id}")
        
        # Test get user sessions
        sessions = get_user_sessions(test_user_id)
        if len(sessions) > 0:
            print(f"✓ Get user sessions works: {len(sessions)} session(s)")
        else:
            print(f"✗ Get user sessions returned empty")
            return False
        
        # Test associate file (need a file first)
        test_content = b"ATOM      1  N   ALA A   1      20.154  16.967  25.468  1.00 30.00           N\n"
        file_metadata = save_uploaded_pdb("test2.pdb", test_content, test_user_id)
        
        associate_file_with_session(
            session_id=session_id,
            file_id=file_metadata['file_id'],
            user_id=test_user_id,
            file_type="upload",
            file_path=file_metadata['stored_path'],
            filename="test2.pdb",
            size=len(test_content),
        )
        print(f"✓ File associated with session")
        
        # Test get session files
        session_files = get_session_files(session_id, test_user_id)
        if len(session_files) > 0:
            print(f"✓ Get session files works: {len(session_files)} file(s)")
        else:
            print(f"✗ Get session files returned empty")
            return False
        
        print("✓ Session tracking tests passed\n")
        return True
    except Exception as e:
        print(f"✗ Session tracking test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_file_access_helpers():
    """Test file access helper functions."""
    print("=" * 60)
    print("Test 4: File Access Helpers")
    print("=" * 60)
    
    test_user_id = "test_user_123"
    test_content = b"ATOM      1  N   ALA A   1      20.154  16.967  25.468  1.00 30.00           N\n"
    
    try:
        # Create a file
        metadata = save_uploaded_pdb("test3.pdb", test_content, test_user_id)
        file_id = metadata['file_id']
        
        # Test ownership verification
        if verify_file_ownership(file_id, test_user_id):
            print(f"✓ Ownership verification works")
        else:
            print(f"✗ Ownership verification failed")
            return False
        
        # Test wrong user
        if not verify_file_ownership(file_id, "wrong_user"):
            print(f"✓ Wrong user correctly denied")
        else:
            print(f"✗ Wrong user incorrectly allowed")
            return False
        
        # Test list user files
        files = list_user_files(test_user_id)
        if len(files) > 0:
            print(f"✓ List user files works: {len(files)} file(s)")
        else:
            print(f"✗ List user files returned empty")
            return False
        
        print("✓ File access helper tests passed\n")
        return True
    except Exception as e:
        print(f"✗ File access helper test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("User Isolation Implementation Tests")
    print("=" * 60 + "\n")
    
    tests = [
        ("Database Tables", test_database_tables),
        ("File Storage", test_file_storage),
        ("Session Tracking", test_session_tracking),
        ("File Access Helpers", test_file_access_helpers),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"✗ {name} test crashed: {e}")
            results.append((name, False))
    
    print("=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = 0
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
        if result:
            passed += 1
    
    print(f"\n{passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {len(results) - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())

