import React from 'react';
import { X, Workflow } from 'lucide-react';
import { usePipelineStore } from '../components/pipeline-canvas/store/pipelineStore';

export const PipelineContextPill: React.FC = () => {
  const { currentPipeline, clearPipeline } = usePipelineStore();
  
  if (!currentPipeline) return null;
  
  return (
    <div className="flex items-center gap-2 px-3 py-1.5 bg-blue-50 border border-blue-200 rounded-full text-sm">
      <Workflow className="w-3.5 h-3.5 text-blue-600" />
      <span className="text-blue-700 font-medium">{currentPipeline.name}</span>
      <button
        onClick={() => clearPipeline()}
        className="ml-1 text-blue-400 hover:text-blue-600 transition-colors"
        title="Clear pipeline context"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
};

