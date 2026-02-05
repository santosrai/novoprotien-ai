# User-Scoped Visualization Code Storage

## Problem Statement

**Mistake to Avoid**: Storing visualization code (Molstar code) using session IDs in the backend.

### Why This Is a Problem

1. **Data Loss on Refresh**: When a user refreshes the page, the session ID may change, causing the visualization code to be lost
2. **No Cross-Session Persistence**: Code is tied to a specific chat session rather than the user
3. **Poor User Experience**: Users lose their work when switching sessions or refreshing

### Previous Implementation (Incorrect)

```typescript
// ❌ WRONG: Session-scoped backend storage
saveVisualizationCode(sessionId, code) {
  // Saved to backend with sessionId as key
  // Lost when session changes or page refreshes
}
```

## Solution: Hybrid Approach

**Key Principle**: **Backend = User-Scoped, LocalStorage = Session-Scoped**

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Data Storage Layers                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Backend (User-Scoped)                                      │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ three_d_canvases table                               │   │
│  │ - Linked to messages via message_id                  │   │
│  │ - Messages have user_id                              │   │
│  │ - Query: WHERE user_id = ? (persists across sessions)│ │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  LocalStorage (Session-Scoped)                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Key: novoprotein-session-code-${sessionId}          │   │
│  │ - Fast cache for current session                    │   │
│  │ - Lost on refresh (but backend has it)              │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Details

### Backend: User-Scoped Endpoints

**File**: `server/api/routes/three_d_canvases.py`

```python
# User-scoped router (NOT session-scoped!)
user_router = APIRouter(prefix="/api/user", tags=["user_canvases"])

@user_router.get("/canvases/latest")
async def get_user_latest_canvas(user: Dict = Depends(get_current_user)):
    """Get latest canvas for current user (user-scoped, not session-scoped!)"""
    user_id = user["id"]
    
    # ✅ CORRECT: Query by user_id through messages
    canvas_row = conn.execute(
        """SELECT c.* FROM three_d_canvases c
           JOIN chat_messages m ON c.message_id = m.id
           WHERE m.user_id = ?  -- User-scoped!
           ORDER BY c.updated_at DESC LIMIT 1""",
        (user_id,)
    ).fetchone()
```

**Key Points**:
- ✅ Always query by `user_id` (through messages)
- ✅ Never use `session_id` as the primary key in backend queries
- ✅ Data persists across sessions because it's linked to user, not session

### Frontend: Hybrid Storage

**File**: `src/stores/chatHistoryStore.ts`

#### Saving Code

```typescript
saveVisualizationCode: async (sessionId, code, messageId?: string) => {
  // 1. Save to session-scoped localStorage cache (for performance)
  if (sessionId) {
    const cacheKey = `novoprotein-session-code-${sessionId}`;
    localStorage.setItem(cacheKey, JSON.stringify({ code, timestamp: ... }));
  }
  
  // 2. Save to backend via message canvas (user-scoped, persists!)
  if (messageId) {
    await api.post(`/conversations/${sessionId}/messages/${messageId}/canvas`, {
      scene_data: code,  // Backend stores this with user_id via message
    });
  }
}
```

#### Loading Code

```typescript
getVisualizationCode: async (sessionId?: string) => {
  // 1. Check session-scoped localStorage cache first (fast)
  if (sessionId) {
    const cached = localStorage.getItem(`novoprotein-session-code-${sessionId}`);
    if (cached) return JSON.parse(cached).code;
  }
  
  // 2. Fallback to backend (user-scoped, always works)
  const response = await api.get('/user/canvases/latest');  // User-scoped!
  const code = response.data.canvas?.sceneData;
  
  // 3. Cache backend result in session localStorage
  if (sessionId && code) {
    localStorage.setItem(`novoprotein-session-code-${sessionId}`, ...);
  }
  
  return code;
}
```

## Data Flow

### Save Flow

```
User saves code
  ↓
1. Save to localStorage (session-scoped cache)
   Key: novoprotein-session-code-${sessionId}
   Purpose: Fast access during current session
  ↓
2. Save to backend (user-scoped persistence)
   Table: three_d_canvases
   Linked via: message_id → chat_messages → user_id
   Purpose: Persists across sessions and refreshes
```

### Load Flow

```
User loads code
  ↓
1. Check session localStorage cache
   Key: novoprotein-session-code-${sessionId}
   If found: Return immediately (fast path)
  ↓
2. If not in cache: Query backend
   Endpoint: GET /api/user/canvases/latest
   Query: WHERE user_id = ? (user-scoped!)
   Returns: Latest code across ALL user's messages
  ↓
3. Cache backend result in session localStorage
   For future fast access during this session
```

### Refresh Flow

```
Page refresh
  ↓
Session localStorage may be cleared
  ↓
Backend still has code (user-scoped!)
  ↓
getVisualizationCode() queries backend
  ↓
Code restored, cached in new session localStorage
```

## Best Practices

### ✅ DO

1. **Always use user_id for backend queries**
   ```python
   # ✅ CORRECT
   WHERE m.user_id = ?
   ```

2. **Use sessionId only for localStorage caching**
   ```typescript
   // ✅ CORRECT
   localStorage.setItem(`novoprotein-session-code-${sessionId}`, ...)
   ```

3. **Query backend by user when session cache is missing**
   ```typescript
   // ✅ CORRECT
   await api.get('/user/canvases/latest')  // User-scoped endpoint
   ```

4. **Link data to messages, which have user_id**
   ```python
   # ✅ CORRECT: Canvas → Message → User
   three_d_canvases.message_id → chat_messages.id → chat_messages.user_id
   ```

### ❌ DON'T

1. **Don't use session_id as primary key in backend**
   ```python
   # ❌ WRONG
   WHERE session_id = ?  # Lost on refresh!
   ```

2. **Don't store user data in session-scoped backend storage**
   ```python
   # ❌ WRONG
   session_state.visualization_code  # Session-scoped, lost on refresh
   ```

3. **Don't query backend by session_id for user data**
   ```typescript
   // ❌ WRONG
   await api.get(`/sessions/${sessionId}/code`)  // Session-scoped!
   ```

4. **Don't assume localStorage persists across refreshes**
   ```typescript
   // ❌ WRONG: Assuming localStorage is enough
   const code = localStorage.getItem('code');  // May be cleared!
   ```

## Database Schema

### Tables Used

```sql
-- Messages (have user_id)
chat_messages (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,  -- ✅ User-scoped!
  session_id TEXT,        -- For organization, not persistence
  ...
)

-- Canvases (linked to messages, inherit user_id)
three_d_canvases (
  id TEXT PRIMARY KEY,
  message_id TEXT REFERENCES chat_messages(id),  -- ✅ Links to user via message
  scene_data TEXT NOT NULL,
  ...
)
```

### Query Pattern

```sql
-- ✅ CORRECT: Get user's latest canvas
SELECT c.* 
FROM three_d_canvases c
JOIN chat_messages m ON c.message_id = m.id
WHERE m.user_id = ?  -- User-scoped!
ORDER BY c.updated_at DESC
LIMIT 1
```

## API Endpoints

### User-Scoped Endpoints (✅ Use These)

- `GET /api/user/canvases/latest` - Get latest canvas for current user
- `GET /api/user/canvases` - Get all canvases for current user

### Message-Scoped Endpoints (For Saving)

- `POST /api/conversations/{conversation_id}/messages/{message_id}/canvas` - Save canvas to message
  - Message has `user_id`, so canvas is user-scoped via message

### Deprecated Endpoints (❌ Avoid)

- `PUT /api/chat/sessions/{session_id}/state` - Session-scoped, deprecated
  - Only use for backward compatibility

## Migration Notes

### Existing Data

- Existing canvases in `three_d_canvases` are already user-scoped (via messages)
- No migration needed - data structure is correct
- Only the query pattern needed to change

### Backward Compatibility

- `saveVisualizationCode(sessionId, code)` still accepts `sessionId` for localStorage caching
- `getVisualizationCode(sessionId?)` accepts optional `sessionId` for cache lookup
- Backend queries always use `user_id`, regardless of `sessionId` parameter

## Testing Checklist

When implementing similar features, verify:

- [ ] Backend queries use `user_id`, not `session_id`
- [ ] Data persists after page refresh
- [ ] Data persists when switching sessions
- [ ] localStorage is used only for caching, not as source of truth
- [ ] Backend is the source of truth for persistence
- [ ] Fallback to backend when localStorage cache is missing

## Common Mistakes to Avoid

1. **Mistake**: Using `session_id` in backend WHERE clauses
   - **Fix**: Always use `user_id` (through messages if needed)

2. **Mistake**: Storing user data in session-scoped tables
   - **Fix**: Store in user-scoped tables or link via user_id

3. **Mistake**: Relying only on localStorage for persistence
   - **Fix**: Use localStorage for caching, backend for persistence

4. **Mistake**: Querying by session_id for user data
   - **Fix**: Query by user_id, use session_id only for localStorage keys

## Summary

**Remember**: 
- **Backend = User-Scoped** (persists across sessions)
- **LocalStorage = Session-Scoped** (fast cache, lost on refresh)
- **Always query by user_id in backend**
- **Use sessionId only for localStorage caching**

This hybrid approach gives you:
- ✅ Persistence across page refreshes
- ✅ Fast local access during session
- ✅ No data loss when sessions change
- ✅ Cross-device persistence (via backend)
