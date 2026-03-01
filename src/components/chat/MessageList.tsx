import React from 'react';
import MessageBubble from './MessageBubble';
import type { ExtendedMessage } from '../../types/chat';

export interface MessageListProps {
  messages: ExtendedMessage[];
  isLoading: boolean;
  hasStreamingContent: boolean;
  messagesEndRef: React.RefObject<HTMLDivElement>;
  plugin: any;
  activeSession: any;
  updateMessages: (msgs: any[]) => void;
  setCurrentCode: (code: string) => void;
  setPendingCodeToRun: (code: string) => void;
  onLoadAlphaFoldInViewer: (result: any, message?: any) => void;
  onLoadSmilesInViewer: (result: any, message?: any) => void;
  onDownloadSmiles: (result: any) => void;
  onLoadOpenFold2InViewer: (result: any, message?: any) => void;
  onLoadDiffDockInViewer: (result: any, message?: any) => void;
  onLoadRFdiffusionInViewer: (result: any, message?: any) => void;
  onLoadFileInViewer: (fileInfo: any) => void;
  onValidateStructure: (pdbContent: string) => void;
  onRetryAlphaFold: (sequence: string, parameters: any) => void;
  setGhostBlueprint: (blueprint: any) => void;
  isValidUploadedFile: (fileInfo: any) => boolean;
  onFetchUniProtEntry: (accession: string) => void;
  onViewPdbStructure: (pdbId: string) => void;
  onCopyMessage: (message: ExtendedMessage) => void | Promise<void>;
  onRetryMessage: (messageId: string) => void | Promise<void>;
  retryingMessageId?: string | null;
}

export function MessageList({
  messages,
  isLoading,
  hasStreamingContent,
  messagesEndRef,
  plugin,
  activeSession,
  updateMessages,
  setCurrentCode,
  setPendingCodeToRun,
  onLoadAlphaFoldInViewer,
  onLoadSmilesInViewer,
  onDownloadSmiles,
  onLoadOpenFold2InViewer,
  onLoadDiffDockInViewer,
  onLoadRFdiffusionInViewer,
  onLoadFileInViewer,
  onValidateStructure,
  onRetryAlphaFold,
  setGhostBlueprint,
  isValidUploadedFile,
  onFetchUniProtEntry,
  onViewPdbStructure,
  onCopyMessage,
  onRetryMessage,
  retryingMessageId,
}: MessageListProps) {
  return (
    <div className="flex-1 overflow-y-auto px-3 py-1.5 space-y-2 min-h-0">
      {messages.map((message) => (
        <MessageBubble
          key={message.id}
          message={message}
          messages={messages}
          plugin={plugin}
          activeSession={activeSession}
          updateMessages={updateMessages}
          setCurrentCode={setCurrentCode}
          setPendingCodeToRun={setPendingCodeToRun}
          onLoadAlphaFoldInViewer={onLoadAlphaFoldInViewer}
          onLoadSmilesInViewer={onLoadSmilesInViewer}
          onDownloadSmiles={onDownloadSmiles}
          onLoadOpenFold2InViewer={onLoadOpenFold2InViewer}
          onLoadDiffDockInViewer={onLoadDiffDockInViewer}
          onLoadRFdiffusionInViewer={onLoadRFdiffusionInViewer}
          onLoadFileInViewer={onLoadFileInViewer}
          onValidateStructure={onValidateStructure}
          onRetryAlphaFold={onRetryAlphaFold}
          setGhostBlueprint={setGhostBlueprint}
          isValidUploadedFile={isValidUploadedFile}
          onFetchUniProtEntry={onFetchUniProtEntry}
          onViewPdbStructure={onViewPdbStructure}
          onCopyMessage={onCopyMessage}
          onRetryMessage={onRetryMessage}
          retryingMessageId={retryingMessageId}
        />
      ))}
      {isLoading && !hasStreamingContent && (
        <div className="flex justify-start">
          <div className="bg-gray-100 px-4 py-3 rounded-2xl rounded-bl-md max-w-xs">
            <div className="flex items-center gap-2.5">
              <div className="flex space-x-1">
                <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce"></div>
                <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0.15s' }}></div>
                <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0.3s' }}></div>
              </div>
              <span className="text-sm text-gray-500 animate-pulse">Thinking...</span>
            </div>
          </div>
        </div>
      )}
      <div ref={messagesEndRef} />
    </div>
  );
}
