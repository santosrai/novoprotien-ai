# Molstar Viewer Initialization and Loading Issues - Fix Documentation

## Overview

This document summarizes the problems encountered with the Molstar viewer initialization, loading states, and file rendering, along with the comprehensive fixes implemented.

## Problems Identified

### 1. Infinite Loading State
**Symptoms:**
- Molstar viewer stuck in "Initializing Molstar Viewer..." state
- Loading spinner never disappears
- Viewer never becomes usable

**Root Causes:**
- `isLoading` state not being cleared in all code execution paths
- Code execution hanging without timeout protection
- Re-initialization loop caused by `activeSessionId` in dependency array
- Blob URL code execution causing errors that prevented completion

### 2. Stale Blob URL Code Restoration
**Symptoms:**
- Code with expired blob URLs appearing in new chats
- Console errors: "Not allowed to load local resource: blob:http://..."
- Viewer trying to execute invalid blob URLs repeatedly

**Root Causes:**
- `getVisualizationCode()` falling back to user-scoped backend code
- Blob URLs expiring after ~5 seconds but being restored from previous sessions
- No detection/filtering of blob URLs in restored code
- Code restoration happening for new sessions that should start empty

### 3. Intermittent "View in 3D" Rendering
**Symptoms:**
- "View in 3D" button sometimes works, sometimes doesn't
- No structure displayed in Molstar canvas
- No code appearing in code editor
- Button click does nothing

**Root Causes:**
- Plugin not fully initialized when button clicked
- Using blob URLs instead of API endpoints
- No plugin readiness check before code execution
- Race conditions between viewer initialization and user actions

### 4. Re-initialization on Session Change
**Symptoms:**
- Viewer re-initializing when switching chat sessions
- Loading state triggered unnecessarily
- Performance issues

**Root Causes:**
- `activeSessionId` in useEffect dependency array causing re-runs
- Viewer should only initialize once, not per session

## Fixes Implemented

### 1. Loading State Management

**File:** `src/components/MolstarViewer.tsx`

**Changes:**
- Added explicit `setIsLoading(false)` in all code execution `finally` blocks
- Added timeout protection for code execution (30 seconds)
- Added initialization timeout warning (10 seconds)
- Removed `activeSessionId` from initialization dependency array

```typescript
// Priority 1 & 2: Ensure loading state cleared
finally {
  setIsExecuting(false);
  setIsLoading(false); // Explicitly clear loading state
}

// Timeout protection
const executionPromise = exec.executeCode(codeToExecute);
const timeoutPromise = new Promise((_, reject) => 
  setTimeout(() => reject(new Error('Code execution timeout after 30 seconds')), 30000)
);
await Promise.race([executionPromise, timeoutPromise]);
```

### 2. Blob URL Detection and Filtering

**Files:** 
- `src/components/MolstarViewer.tsx`
- `src/components/ChatPanel.tsx`

**Changes:**
- Created `hasBlobUrl()` helper function to detect blob URLs
- Filter blob URLs in `getCodeToExecute()` before returning code
- Clear blob URLs from `currentCode` when detected
- Skip blob URL code in persisted code check
- Cleanup blob URLs on session change

```typescript
// Helper function to detect blob URLs
const hasBlobUrl = (code: string): boolean => {
  return code.includes('blob:http://') || code.includes('blob:https://');
};

// Filter in getCodeToExecute()
if (currentCode && currentCode.trim()) {
  if (hasBlobUrl(currentCode)) {
    console.warn('[Molstar] Current code contains blob URL (expired), ignoring');
    return null;
  }
  return currentCode;
}
```

### 3. New Chat Code Restoration Fix

**File:** `src/components/ChatPanel.tsx`

**Changes:**
- Detect new sessions (no messages) and skip code restoration
- Clear code for new sessions instead of restoring from backend
- Invalidate blob URLs in restored code

```typescript
// Check if this is a new session (no messages)
const isNewSession = !activeSession || activeSession.messages.length === 0;

if (isNewSession) {
  // For new sessions, clear any existing code
  if (currentCodeRef.current && currentCodeRef.current.trim()) {
    console.log('[ChatPanel] Clearing code for new session:', activeSessionId);
    setCurrentCode('');
  }
} else {
  // Only restore code for existing sessions with messages
  // ... with blob URL detection
}
```

### 4. Plugin Readiness and API Endpoint Usage

**Files:**
- `src/components/ChatPanel.tsx`
- `src/components/FileEditor.tsx`

**Changes:**
- Added `waitForPlugin()` function to check plugin readiness
- Use API endpoints directly instead of blob URLs
- Queue code execution if plugin not ready
- Better error handling

```typescript
// Wait for plugin to be ready
const waitForPlugin = async (maxWait = 5000, retryInterval = 100): Promise<boolean> => {
  const startTime = Date.now();
  while (Date.now() - startTime < maxWait) {
    if (plugin) {
      try {
        if (plugin.builders && plugin.builders.data && plugin.builders.structure) {
          return true;
        }
      } catch (e) {
        // Plugin exists but might not be fully ready
      }
    }
    await new Promise(resolve => setTimeout(resolve, retryInterval));
  }
  return false;
};

// Use API endpoint directly
const apiUrl = `/api/upload/pdb/${fileId}`;
const code = `
try {
  await builder.clearStructure();
  await builder.loadStructure('${apiUrl}');
  await builder.addCartoonRepresentation({ color: 'secondary-structure' });
  builder.focusView();
} catch (e) { 
  console.error('Failed to load file:', e); 
}`;
```

### 5. Fallback Code for New Chats

**File:** `src/components/MolstarViewer.tsx`

**Changes:**
- Changed fallback code from `clearStructure()` to `focusView()`
- Added timeout protection for fallback code

```typescript
// Priority 3: Fallback for new chat
if (isNewChat) {
  try {
    const exec = new CodeExecutor(pluginInstance);
    const fallbackPromise = exec.executeCode(`try {
  builder.focusView();
} catch (e) { 
  console.error(e); 
}`);
    const timeoutPromise = new Promise((_, reject) => 
      setTimeout(() => reject(new Error('Fallback code timeout after 5 seconds')), 5000)
    );
    await Promise.race([fallbackPromise, timeoutPromise]);
  } catch (e) {
    console.error('[Molstar] Failed to run fallback code: ', e);
  }
}
```

### 6. Persisted Code Check Timeout

**File:** `src/components/MolstarViewer.tsx`

**Changes:**
- Added fallback timeout to prevent infinite waiting
- Always set `hasCheckedPersistedCode` after max 2 seconds

```typescript
// Fallback: always set hasCheckedPersistedCode after max 2 seconds
const fallbackTimer = setTimeout(() => {
  if (!hasCheckedPersistedCode) {
    console.warn('[Molstar] Persisted code check timeout, proceeding with initialization');
    setHasCheckedPersistedCode(true);
  }
}, 2000);
```

## Best Practices Going Forward

### 1. Always Use API Endpoints for File Loading
**DO:**
```typescript
const apiUrl = `/api/upload/pdb/${fileId}`;
await builder.loadStructure(apiUrl);
```

**DON'T:**
```typescript
// Don't create blob URLs for file loading
const blobUrl = URL.createObjectURL(pdbBlob);
await builder.loadStructure(blobUrl);
```

### 2. Check Plugin Readiness Before Execution
**DO:**
```typescript
const waitForPlugin = async () => {
  // Check plugin.builders.data and plugin.builders.structure
  if (plugin?.builders?.data && plugin?.builders?.structure) {
    return true;
  }
  return false;
};
```

**DON'T:**
```typescript
// Don't assume plugin is ready just because it exists
if (!plugin) return; // Not enough!
```

### 3. Always Clear Loading States
**DO:**
```typescript
try {
  setIsLoading(true);
  // ... execute code
} finally {
  setIsLoading(false); // Always clear in finally block
}
```

### 4. Filter Blob URLs in Code
**DO:**
```typescript
const hasBlobUrl = (code: string): boolean => {
  return code.includes('blob:http://') || code.includes('blob:https://');
};

if (hasBlobUrl(code)) {
  // Skip or clear blob URL code
  return null;
}
```

### 5. Use Timeout Protection
**DO:**
```typescript
const executionPromise = exec.executeCode(code);
const timeoutPromise = new Promise((_, reject) => 
  setTimeout(() => reject(new Error('Timeout')), 30000)
);
await Promise.race([executionPromise, timeoutPromise]);
```

### 6. Queue Code if Plugin Not Ready
**DO:**
```typescript
if (!isPluginReady) {
  setPendingCodeToRun(code);
  return;
}
```

## Testing Checklist

When testing Molstar viewer functionality:

- [ ] New chat starts with empty viewer (no stale code)
- [ ] "View in 3D" button works consistently
- [ ] Loading state clears after initialization
- [ ] No blob URL errors in console
- [ ] Code appears in code editor when loading files
- [ ] Viewer doesn't re-initialize on session switch
- [ ] Files load successfully using API endpoints
- [ ] Plugin readiness is checked before execution

## Related Files Modified

1. `src/components/MolstarViewer.tsx` - Main viewer component
2. `src/components/ChatPanel.tsx` - Chat interface with file uploads
3. `src/components/FileEditor.tsx` - File editor with 3D view button
4. `src/stores/chatHistoryStore.ts` - Session management (code restoration logic)

## Future Improvements

1. **Plugin State Management**: Consider adding plugin readiness state to appStore
2. **Error Recovery**: Add retry mechanism for failed code execution
3. **Code Validation**: Validate code before execution to catch issues early
4. **Performance**: Optimize plugin initialization to reduce wait times
5. **User Feedback**: Show loading progress for long-running operations

## Notes

- Blob URLs should only be used for temporary, in-memory data
- API endpoints are more reliable and don't expire
- Always check plugin readiness before executing code
- Loading states must be cleared in all code paths
- New sessions should start clean, without restored code
