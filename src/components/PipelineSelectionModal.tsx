import React from 'react';
import { usePipelineStore } from '../components/pipeline-canvas';
import { X, FileText } from 'lucide-react';

interface PipelineSelectionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onPipelineSelect?: (pipelineId: string) => void;
}

export const PipelineSelectionModal: React.FC<PipelineSelectionModalProps> = ({
  isOpen,
  onClose,
  onPipelineSelect,
}) => {
  const { savedPipelines, loadPipeline } = usePipelineStore();

  if (!isOpen) return null;

  const formatDate = (date: Date): string => {
    const d = new Date(date);
    const months = [
      'January', 'February', 'March', 'April', 'May', 'June',
      'July', 'August', 'September', 'October', 'November', 'December'
    ];
    return `Created ${months[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()}`;
  };

  const handlePipelineClick = (pipelineId: string) => {
    loadPipeline(pipelineId);
    onPipelineSelect?.(pipelineId);
    onClose();
  };

  // Sort pipelines by creation date (most recent first)
  const sortedPipelines = [...savedPipelines].sort((a, b) => {
    const dateA = new Date(a.createdAt).getTime();
    const dateB = new Date(b.createdAt).getTime();
    return dateB - dateA;
  });

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="bg-[#1e1e32] rounded-lg shadow-xl w-full max-w-md max-h-[80vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-700/50">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center">
              <FileText className="w-4 h-4 text-white" />
            </div>
            <h2 className="text-lg font-semibold text-white">Add pipeline</h2>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center text-gray-400 hover:text-white hover:bg-gray-700/50 rounded-full transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4">
          <div className="mb-3">
            <h3 className="text-sm font-medium text-gray-400 mb-2">Recent</h3>
          </div>

          {sortedPipelines.length === 0 ? (
            <div className="text-center py-8">
              <p className="text-sm text-gray-500">No saved pipelines</p>
              <p className="text-xs text-gray-600 mt-1">Create a pipeline to see it here</p>
            </div>
          ) : (
            <div className="space-y-2">
              {sortedPipelines.map((pipeline) => {
                const nodeCount = pipeline.nodes.length;
                return (
                  <div
                    key={pipeline.id}
                    onClick={() => handlePipelineClick(pipeline.id)}
                    className="flex items-center gap-3 p-3 rounded-lg hover:bg-gray-800/50 cursor-pointer transition-colors group"
                  >
                    <div className="w-10 h-10 flex items-center justify-center bg-gray-700/50 rounded group-hover:bg-gray-700 transition-colors">
                      <FileText className="w-5 h-5 text-gray-400" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h4 className="text-sm font-medium text-white truncate">
                        {pipeline.name}
                      </h4>
                      <p className="text-xs text-gray-500 mt-0.5">
                        {nodeCount} {nodeCount === 1 ? 'node' : 'nodes'} • {formatDate(pipeline.createdAt)}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

