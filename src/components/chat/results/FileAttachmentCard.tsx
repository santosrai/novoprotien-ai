import React from 'react';
import { Play } from 'lucide-react';
import type { ExtendedMessage } from '../../../types/chat';

type UploadedFile = NonNullable<ExtendedMessage['uploadedFile']>;

interface Props {
  fileInfo: UploadedFile;
  isUserMessage?: boolean;
  onLoadInViewer: (fileInfo: UploadedFile) => void;
}

const FileAttachmentCard: React.FC<Props> = ({ fileInfo, isUserMessage = false, onLoadInViewer }) => {
  const bgClass = isUserMessage 
    ? 'bg-white bg-opacity-20 border-white border-opacity-30' 
    : 'bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200';
  const textClass = isUserMessage ? 'text-white' : 'text-gray-900';
  const textSecondaryClass = isUserMessage ? 'text-white text-opacity-80' : 'text-gray-600';
  const buttonClass = isUserMessage
    ? 'bg-white text-blue-600 hover:bg-gray-100'
    : 'bg-blue-600 text-white hover:bg-blue-700';

  return (
    <div className={`mt-3 p-4 ${bgClass} rounded-lg`}>
      <div className="flex items-center space-x-2 mb-3">
        <div className={`w-8 h-8 ${isUserMessage ? 'bg-white bg-opacity-30' : 'bg-blue-600'} rounded-full flex items-center justify-center`}>
          <span className={`${isUserMessage ? 'text-white' : 'text-white'} text-sm font-bold`}>PDB</span>
        </div>
        <div>
          <h4 className={`font-medium ${textClass}`}>Uploaded PDB File</h4>
          <p className={`text-xs ${textSecondaryClass}`}>
            {fileInfo.filename} • {fileInfo.atoms} atoms • {fileInfo.chains.length} chain{fileInfo.chains.length !== 1 ? 's' : ''}
          </p>
        </div>
      </div>
      
      {fileInfo.chains.length > 0 && (
        <div className={`mb-3 text-xs ${textSecondaryClass}`}>
          <span>Chains: {fileInfo.chains.join(', ')}</span>
        </div>
      )}
      
      <div className="flex space-x-2">
        <button
          onClick={() => onLoadInViewer(fileInfo)}
          className={`flex items-center space-x-1 px-3 py-2 ${buttonClass} rounded-md text-sm`}
        >
          <Play className="w-4 h-4" />
          <span>View in 3D</span>
        </button>
      </div>
    </div>
  );
};

export default FileAttachmentCard;
