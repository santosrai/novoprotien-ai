import React from 'react';
import type { ExtendedMessage } from '../../../types/chat';

interface Props {
  pipeline: ExtendedMessage['pipeline'];
  isUserMessage?: boolean;
}

const PipelineAttachmentCard: React.FC<Props> = ({ pipeline, isUserMessage = false }) => {
  if (!pipeline) return null;

  const bgClass = isUserMessage 
    ? 'bg-white bg-opacity-20 border-white border-opacity-30' 
    : 'bg-gradient-to-r from-purple-50 to-indigo-50 border border-purple-200';
  const textClass = isUserMessage ? 'text-white' : 'text-gray-900';
  const textSecondaryClass = isUserMessage ? 'text-white text-opacity-80' : 'text-gray-600';

  const statusColors: Record<string, string> = {
    draft: 'bg-gray-100 text-gray-700',
    running: 'bg-blue-100 text-blue-700',
    completed: 'bg-green-100 text-green-700',
    failed: 'bg-red-100 text-red-700',
  };

  return (
    <div className={`mt-3 p-4 ${bgClass} rounded-lg`}>
      <div className="flex items-center space-x-2 mb-3">
        <div className={`w-8 h-8 ${isUserMessage ? 'bg-white bg-opacity-30' : 'bg-purple-600'} rounded-full flex items-center justify-center`}>
          <span className={`${isUserMessage ? 'text-white' : 'text-white'} text-sm font-bold`}>⚙️</span>
        </div>
        <div className="flex-1">
          <h4 className={`font-medium ${textClass}`}>Pipeline: {pipeline.name}</h4>
          <div className="flex items-center gap-2 mt-1">
            <span className={`text-xs px-2 py-0.5 rounded-full ${statusColors[pipeline.status] || statusColors.draft}`}>
              {pipeline.status}
            </span>
          </div>
        </div>
      </div>
      <p className={`text-xs ${textSecondaryClass} mt-2`}>
        Ask questions about this pipeline's nodes, execution history, or output files.
      </p>
    </div>
  );
};

export default PipelineAttachmentCard;
