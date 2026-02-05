# Chat History User Isolation Fix

## Problem
All users were seeing the same chat history because:
1. Chat history was stored in `localStorage` with a fixed key: `'novoprotein-chat-history-storage'`
2. All users on the same browser shared the same localStorage
3. No user-scoping was applied

## Solution Implemented

### 1. Database Schema
Added `chat_messages` table to store message content:
```sql
CREATE TABLE chat_messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    content TEXT NOT NULL,
    message_type TEXT NOT NULL DEFAULT 'user',
    role TEXT,
    metadata TEXT, -- JSON: jobId, jobType, thinkingProcess, results, etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

### 2. Backend API Endpoints
Created `/api/chat/sessions/{session_id}/messages` endpoints:
- `POST /` - Create message
- `GET /` - List messages
- `GET /{message_id}` - Get message
- `PUT /{message_id}` - Update message
- `DELETE /{message_id}` - Delete message

All endpoints verify session ownership before allowing access.

### 3. Frontend User-Scoped Storage
Updated `chatHistoryStore.ts` to use user-specific localStorage keys:
- Before: `'novoprotein-chat-history-storage'` (shared)
- After: `'novoprotein-chat-history-{userId}'` (user-specific)

This ensures each user has their own localStorage namespace.

## Files Modified

### Backend
- `server/database/schema.sql` - Added `chat_messages` table
- `server/api/routes/chat_messages.py` - New message API endpoints
- `server/app.py` - Registered chat_messages router
- `server/api/routes/__init__.py` - Added chat_messages to exports

### Frontend
- `src/stores/chatHistoryStore.ts` - Updated to use user-scoped localStorage keys

## How It Works

1. **User-Scoped localStorage**: Each user gets their own localStorage key based on their user ID
   ```typescript
   const userKey = `novoprotein-chat-history-${userId}`;
   ```

2. **Backend Storage**: Messages are stored in the database with `user_id` foreign key
   - Ensures data persistence across devices
   - Enables future sync functionality
   - Provides proper access control

3. **Access Control**: All API endpoints verify:
   - User is authenticated
   - Session belongs to the user
   - Message belongs to the session

## Testing

To verify the fix:
1. Sign in as User A
2. Create some chat messages
3. Sign out
4. Sign in as User B
5. User B should NOT see User A's messages

## Next Steps (Future Enhancement)

For full backend sync:
1. Update `chatHistoryStore` to sync sessions with `/api/chat/sessions`
2. Update `chatHistoryStore` to sync messages with `/api/chat/sessions/{id}/messages`
3. Implement periodic sync or sync on session switch
4. Use backend as source of truth, localStorage as cache

## Status

✅ **Fixed**: Chat history is now user-scoped
- Each user sees only their own chat history
- localStorage keys are user-specific
- Backend API ready for full sync implementation

