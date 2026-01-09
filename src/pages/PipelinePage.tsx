import { useEffect, useState } from 'react';
import { PipelineCanvas, PipelineManager, PipelineExecution } from '../components/pipeline-canvas';
import { usePipelineStore } from '../components/pipeline-canvas/store/pipelineStore';
import { useAuthStore } from '../stores/authStore';
import { api } from '../utils/api';

export function PipelinePage() {
  const [isPipelineManagerOpen, setIsPipelineManagerOpen] = useState(false);
  const { syncPipelines } = usePipelineStore();
  const user = useAuthStore((state) => state.user);

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
    <div className="h-screen w-screen flex flex-col bg-[#1a1a2e]">
      {/* Optional minimal header for standalone view */}
      <div className="h-12 flex items-center justify-between px-4 bg-gray-900 border-b border-gray-800">
        <h1 className="text-white text-lg font-semibold">Pipeline Canvas</h1>
        <a 
          href="/app" 
          className="text-gray-400 hover:text-white text-sm transition-colors"
        >
          ← Back to Main App
        </a>
      </div>
      
      {/* Full-screen pipeline canvas */}
      <div className="flex-1 min-h-0">
        <PipelineCanvas />
      </div>
      
      {/* Pipeline Manager Modal */}
      <PipelineManager
        isOpen={isPipelineManagerOpen}
        onClose={() => setIsPipelineManagerOpen(false)}
      />
      
      {/* Pipeline Execution Monitor */}
      <PipelineExecution apiClient={api} />
    </div>
  );
}


