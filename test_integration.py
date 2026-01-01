#!/usr/bin/env python3
"""
Integration test for user isolation implementation.
Tests the core functionality without requiring a running server.
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path
import json

# Setup paths
server_dir = Path(__file__).parent / "server"
sys.path.insert(0, str(server_dir))

# Mock infrastructure.config
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

# Now import our modules
from database.db import get_db, init_db
from domain.storage.pdb_storage import save_uploaded_pdb, get_uploaded_pdb, list_uploaded_pdbs, delete_uploaded_pdb
from domain.storage.session_tracker import create_chat_session, get_user_sessions, associate_file_with_session, get_session_files, remove_file_from_session
from domain.storage.file_access import verify_file_ownership, list_user_files, save_result_file

def test_database_setup():
    """Test database initialization."""
    print("=" * 60)
    print("Test 1: Database Setup")
    print("=" * 60)
    
    try:
        # Check tables exist
        with get_db() as conn:
            tables = ['user_files', 'chat_sessions', 'session_files', 'pipelines', 'pipeline_executions']
            for table in tables:
                result = conn.execute(
                    f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'"
                ).fetchone()
                if not result:
                    print(f"✗ Table '{table}' not found")
                    return False
                print(f"  ✓ Table '{table}' exists")
        
        print("✓ Database setup verified\n")
        return True
    except Exception as e:
        print(f"✗ Database setup failed: {e}")
        return False

def test_file_storage():
    """Test user-scoped file storage."""
    print("=" * 60)
    print("Test 2: File Storage (User Isolation)")
    print("=" * 60)
    
    test_user_id = "test_user_001"
    test_content = b"""HEADER    TEST PROTEIN                          01-JAN-24   TEST
ATOM      1  N   ALA A   1      20.154  16.967  25.468  1.00 30.00           N
ATOM      2  CA  ALA A   1      18.923  17.723  25.468  1.00 30.00           C
END
"""
    test_filename = "test_protein.pdb"
    
    try:
        # Test 1: Save file
        print("  Testing file save...")
        metadata = save_uploaded_pdb(test_filename, test_content, test_user_id)
        file_id = metadata['file_id']
        print(f"    ✓ File saved: {file_id}")
        
        # Verify file exists in user directory
        stored_path = Path(server_dir) / metadata['stored_path']
        if stored_path.exists():
            print(f"    ✓ File exists at: {stored_path}")
        else:
            print(f"    ✗ File not found at: {stored_path}")
            return False
        
        # Test 2: Get file with correct user
        print("  Testing file retrieval (correct user)...")
        retrieved = get_uploaded_pdb(file_id, test_user_id)
        if retrieved and retrieved.get('file_id') == file_id:
            print(f"    ✓ File retrieved successfully")
        else:
            print(f"    ✗ File retrieval failed")
            return False
        
        # Test 3: Get file with wrong user (should fail)
        print("  Testing ownership verification (wrong user)...")
        wrong_user_result = get_uploaded_pdb(file_id, "wrong_user_999")
        if wrong_user_result is None:
            print(f"    ✓ Ownership check works (wrong user denied)")
        else:
            print(f"    ✗ Ownership check failed (wrong user got file)")
            return False
        
        # Test 4: List user files
        print("  Testing list user files...")
        files = list_uploaded_pdbs(test_user_id)
        if len(files) > 0 and any(f.get('file_id') == file_id for f in files):
            print(f"    ✓ List files works: {len(files)} file(s)")
        else:
            print(f"    ✗ List files failed")
            return False
        
        # Test 5: Delete file
        print("  Testing file deletion...")
        delete_uploaded_pdb(file_id, test_user_id)
        deleted_check = get_uploaded_pdb(file_id, test_user_id)
        if deleted_check is None:
            print(f"    ✓ File deleted successfully")
        else:
            print(f"    ✗ File deletion failed")
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
    print("Test 3: Session Tracking")
    print("=" * 60)
    
    test_user_id = "test_user_002"
    
    try:
        # Test 1: Create session
        print("  Testing session creation...")
        session_id = create_chat_session(test_user_id, "Test Chat Session")
        print(f"    ✓ Session created: {session_id}")
        
        # Test 2: Get user sessions
        print("  Testing get user sessions...")
        sessions = get_user_sessions(test_user_id)
        if len(sessions) > 0 and any(s.get('id') == session_id for s in sessions):
            print(f"    ✓ Get user sessions works: {len(sessions)} session(s)")
        else:
            print(f"    ✗ Get user sessions failed")
            return False
        
        # Test 3: Associate file with session
        print("  Testing file association...")
        test_content = b"ATOM      1  N   ALA A   1      20.154  16.967  25.468  1.00 30.00           N\n"
        file_metadata = save_uploaded_pdb("session_test.pdb", test_content, test_user_id)
        
        associate_file_with_session(
            session_id=session_id,
            file_id=file_metadata['file_id'],
            user_id=test_user_id,
            file_type="upload",
            file_path=file_metadata['stored_path'],
            filename="session_test.pdb",
            size=len(test_content),
        )
        print(f"    ✓ File associated with session")
        
        # Test 4: Get session files
        print("  Testing get session files...")
        session_files = get_session_files(session_id, test_user_id)
        if len(session_files) > 0:
            print(f"    ✓ Get session files works: {len(session_files)} file(s)")
        else:
            print(f"    ✗ Get session files failed")
            return False
        
        # Test 5: Remove file from session
        print("  Testing remove file from session...")
        remove_file_from_session(session_id, file_metadata['file_id'], test_user_id)
        remaining_files = get_session_files(session_id, test_user_id)
        if len(remaining_files) == 0:
            print(f"    ✓ Remove file from session works")
        else:
            print(f"    ✗ Remove file from session failed")
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
    
    test_user_id = "test_user_003"
    test_content = b"ATOM      1  N   ALA A   1      20.154  16.967  25.468  1.00 30.00           N\n"
    
    try:
        # Test 1: Save result file
        print("  Testing save result file...")
        file_id = "test_result_001"
        filepath = save_result_file(
            user_id=test_user_id,
            file_id=file_id,
            file_type="rfdiffusion",
            filename="rfdiffusion_test.pdb",
            content=test_content,
            job_id=file_id,
            metadata={"test": "data"}
        )
        print(f"    ✓ Result file saved: {filepath}")
        
        # Test 2: Verify ownership
        print("  Testing ownership verification...")
        if verify_file_ownership(file_id, test_user_id):
            print(f"    ✓ Ownership verification works")
        else:
            print(f"    ✗ Ownership verification failed")
            return False
        
        # Test 3: Wrong user denied
        print("  Testing wrong user denial...")
        if not verify_file_ownership(file_id, "wrong_user"):
            print(f"    ✓ Wrong user correctly denied")
        else:
            print(f"    ✗ Wrong user incorrectly allowed")
            return False
        
        # Test 4: List user files
        print("  Testing list user files...")
        files = list_user_files(test_user_id, file_type="rfdiffusion")
        if len(files) > 0:
            print(f"    ✓ List user files works: {len(files)} file(s)")
        else:
            print(f"    ✗ List user files failed")
            return False
        
        print("✓ File access helper tests passed\n")
        return True
    except Exception as e:
        print(f"✗ File access helper test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_pipeline_api_structure():
    """Test that pipeline API routes are properly structured."""
    print("=" * 60)
    print("Test 5: Pipeline API Structure")
    print("=" * 60)
    
    try:
        # Check if pipeline routes file exists and has required functions
        pipeline_routes = server_dir / "api" / "routes" / "pipelines.py"
        if not pipeline_routes.exists():
            print(f"    ✗ Pipeline routes file not found")
            return False
        
        with open(pipeline_routes, 'r') as f:
            content = f.read()
        
        required_endpoints = [
            "@router.post",
            "@router.get",
            "@router.put",
            "@router.delete",
            "get_current_user",
        ]
        
        for endpoint in required_endpoints:
            if endpoint in content:
                print(f"    ✓ Found: {endpoint}")
            else:
                print(f"    ✗ Missing: {endpoint}")
                return False
        
        print("✓ Pipeline API structure verified\n")
        return True
    except Exception as e:
        print(f"✗ Pipeline API structure test failed: {e}")
        return False

def test_chat_session_api_structure():
    """Test that chat session API routes are properly structured."""
    print("=" * 60)
    print("Test 6: Chat Session API Structure")
    print("=" * 60)
    
    try:
        # Check if chat session routes file exists
        chat_routes = server_dir / "api" / "routes" / "chat_sessions.py"
        if not chat_routes.exists():
            print(f"    ✗ Chat session routes file not found")
            return False
        
        with open(chat_routes, 'r') as f:
            content = f.read()
        
        required_endpoints = [
            "@router.post",
            "@router.get",
            "@router.put",
            "@router.delete",
            "get_current_user",
        ]
        
        for endpoint in required_endpoints:
            if endpoint in content:
                print(f"    ✓ Found: {endpoint}")
            else:
                print(f"    ✗ Missing: {endpoint}")
                return False
        
        print("✓ Chat session API structure verified\n")
        return True
    except Exception as e:
        print(f"✗ Chat session API structure test failed: {e}")
        return False

def main():
    """Run all integration tests."""
    print("\n" + "=" * 60)
    print("User Isolation - Integration Tests")
    print("=" * 60 + "\n")
    
    tests = [
        ("Database Setup", test_database_setup),
        ("File Storage", test_file_storage),
        ("Session Tracking", test_session_tracking),
        ("File Access Helpers", test_file_access_helpers),
        ("Pipeline API Structure", test_pipeline_api_structure),
        ("Chat Session API Structure", test_chat_session_api_structure),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"✗ {name} test crashed: {e}")
            import traceback
            traceback.print_exc()
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
        print("\n🎉 All integration tests passed!")
        print("\nThe user isolation implementation is working correctly.")
        return 0
    else:
        print(f"\n⚠️  {len(results) - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())

