# React Query Migration Status

## Completed ✅

### 1. Setup & Configuration
- ✅ Installed `@tanstack/react-query`
- ✅ Created `src/utils/queryClient.ts` with QueryClient configuration
- ✅ Created `src/utils/queryErrorHandler.ts` for global error handling
- ✅ Wrapped app with `QueryClientProvider` in `src/main.tsx`

### 2. Query Hooks (GET Requests)
- ✅ `useModels` - Fetch available models
- ✅ `useAgents` - Fetch available agents
- ✅ `useFiles` - List user files
- ✅ `useFile` - Get single file metadata
- ✅ `usePipelines` - List user pipelines
- ✅ `usePipeline` - Get single pipeline
- ✅ `useChatSessions` - List chat sessions
- ✅ `useChatSession` - Get single chat session with messages
- ✅ `useJobStatus` - Poll job status with refetchInterval

### 3. Mutation Hooks (POST/PUT/DELETE)
- ✅ `useSignIn`, `useSignUp`, `useSignOut`, `useRefreshToken` - Authentication
- ✅ `useFileUpload`, `useFileDelete` - File operations
- ✅ `useCreatePipeline`, `useUpdatePipeline`, `useDeletePipeline` - Pipeline CRUD
- ✅ `useCreateChatSession`, `useCreateChatMessage`, `useUpdateChatSession` - Chat operations
- ✅ `useStreamAgentRoute` - Streaming agent responses
- ✅ `useAlphaFoldFold`, `useAlphaFoldCancel` - AlphaFold operations
- ✅ `useRFdiffusionDesign`, `useRFdiffusionCancel` - RFdiffusion operations

### 4. Component Migrations
- ✅ `FileBrowser` - Migrated to use `useFiles` and `useFileDelete`
- ✅ `JobLoadingPill` - Migrated to use `useJobStatus` with React Query polling

### 5. Global Error Handling
- ✅ Implemented global error handler for 401, 402, 403, network errors
- ✅ Integrated with existing error system
- ✅ Retry logic with exponential backoff

## Partially Complete / Remaining 🔄

### Component Migrations (High Priority)
- ⏳ `ChatPanel` - Complex component with streaming, needs incremental migration
- ⏳ `PipelineStore` (Zustand) - Needs refactoring to use React Query hooks
- ⏳ `SignInForm` / `SignUpForm` - Can use React Query hooks but currently using authStore (works fine)

### Component Migrations (Medium Priority)
- ⏳ `AlphaFoldDialog` - Can use `useAlphaFoldFold` mutation
- ⏳ `RFdiffusionDialog` - Can use `useRFdiffusionDesign` mutation
- ⏳ `ProteinMPNNDialog` - Needs mutation hook (not yet created)
- ⏳ Admin dashboard components - Can use query hooks

### Zustand Store Refactoring
- ⏳ `chatHistoryStore` - Remove `syncSessions`, `loadSession`, `saveSession` API calls
- ⏳ `pipelineStore` - Remove `syncPipelines`, `loadPipeline`, `savePipeline` API calls
- ⏳ `authStore` - Keep for now (client state), but can use React Query mutations

### Cleanup
- ⏳ Remove `JobPoller` class (deprecated, replaced by `useJobStatus`)
- ⏳ Remove manual API calls in components
- ⏳ Update documentation

## Usage Examples

### Using Query Hooks
```typescript
import { useFiles } from '../hooks/queries/useFiles';

function MyComponent() {
  const { data: files, isLoading, error } = useFiles();
  
  if (isLoading) return <div>Loading...</div>;
  if (error) return <div>Error: {error.message}</div>;
  
  return <div>{files.map(file => <div key={file.file_id}>{file.filename}</div>)}</div>;
}
```

### Using Mutation Hooks
```typescript
import { useFileUpload } from '../hooks/mutations/useFileUpload';

function UploadComponent() {
  const upload = useFileUpload();
  
  const handleUpload = async (file: File) => {
    try {
      await upload.mutateAsync({ file });
      console.log('Upload successful!');
    } catch (error) {
      console.error('Upload failed:', error);
    }
  };
  
  return (
    <button onClick={() => handleUpload(file)} disabled={upload.isPending}>
      {upload.isPending ? 'Uploading...' : 'Upload'}
    </button>
  );
}
```

### Using Job Status Polling
```typescript
import { useJobStatus } from '../hooks/queries/useJobStatus';

function JobTracker({ jobId }: { jobId: string }) {
  const { data: status } = useJobStatus(jobId, 'alphafold', {
    refetchInterval: 3000, // Poll every 3 seconds
  });
  
  return <div>Progress: {status?.progress || 0}%</div>;
}
```

## Next Steps

1. **Incremental Component Migration**: Migrate remaining components one at a time
2. **Zustand Refactoring**: Gradually remove server state from Zustand stores
3. **Testing**: Test all migrated components thoroughly
4. **Cleanup**: Remove deprecated code and update documentation

## Notes

- React Query hooks are ready to use throughout the application
- Components can be migrated incrementally without breaking existing functionality
- Auth store can continue using existing methods, React Query hooks are available as alternatives
- Streaming is handled via `useStreamAgentRoute` mutation hook
- Polling is handled via `useJobStatus` with `refetchInterval`
