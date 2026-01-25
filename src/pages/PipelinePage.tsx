import { useEffect, useState } from 'react';
import { PipelineCanvas, PipelineManager, PipelineExecution, PipelineThemeWrapper, PipelineProvider } from '../components/pipeline-canvas';
import { usePipelineStore } from '../components/pipeline-canvas/store/pipelineStore';
import { useAuthStore } from '../stores/authStore';
import { api, getAuthHeaders } from '../utils/api';
import { useTheme } from '../contexts/ThemeContext';

export function PipelinePage() {
  const [isPipelineManagerOpen, setIsPipelineManagerOpen] = useState(false);
  const { syncPipelines } = usePipelineStore();
  const user = useAuthStore((state) => state.user);
  const { theme } = useTheme();

  // Sync pipelines from backend when component mounts and user is authenticated
  useEffect(() => {
    if (user) {
      console.log('[PipelinePage] Syncing pipelines from backend...');
      syncPipelines().catch((error) => {
        console.error('[PipelinePage] Failed to sync pipelines:', error);
      });
    }
  }, [user, syncPipelines]);

  // Listen for pipeline manager open event
  useEffect(() => {
    const handleOpenPipelineManager = () => {
      setIsPipelineManagerOpen(true);
    };
    window.addEventListener('open-pipeline-manager', handleOpenPipelineManager);
    return () => window.removeEventListener('open-pipeline-manager', handleOpenPipelineManager);
  }, []);

  return (
    <div className="h-screen w-screen flex flex-col bg-app text-app">
      {/* Optional minimal header for standalone view */}
      <div className="h-12 flex items-center justify-between px-4 bg-app-card border-b border-app">
        <h1 className="text-app text-lg font-semibold">Pipeline Canvas</h1>
        <a 
          href="/app" 
          className="text-app-muted hover:text-app text-sm transition-colors"
        >
          ← Back to Main App
        </a>
      </div>
      
      {/* Full-screen pipeline canvas with provider for API/auth and sync */}
      <PipelineProvider
        apiClient={api}
        authState={{ user: user ?? null, isAuthenticated: !!user }}
        getAuthHeaders={getAuthHeaders}
      >
        <div className="flex-1 min-h-0">
          <PipelineThemeWrapper externalTheme={theme} className="h-full">
            <PipelineCanvas />
          </PipelineThemeWrapper>
        </div>

        {/* Pipeline Manager Modal */}
        <PipelineManager
          isOpen={isPipelineManagerOpen}
          onClose={() => setIsPipelineManagerOpen(false)}
        />

        {/* Pipeline Execution Monitor */}
        <PipelineExecution apiClient={api} />
      </PipelineProvider>
    </div>
  );
}


