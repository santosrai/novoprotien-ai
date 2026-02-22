import React from 'react';
import { Send, ChevronDown, ChevronUp, X } from 'lucide-react';
import { AgentSelector } from '../AgentSelector';
import { ModelSelector } from '../ModelSelector';
import { AttachmentMenu } from '../AttachmentMenu';
import { ProgressTracker } from '../ProgressTracker';
import type { FileUploadState } from '../../types/chat';

interface ChatInputProps {
  input: string;
  setInput: (v: string) => void;
  isLoading: boolean;
  showCenteredLayout: boolean;
  selections: any[];
  removeSelection: (index: number) => void;
  clearSelections: () => void;
  formatSelection: (sel: any) => string;
  fileUploads: FileUploadState[];
  setFileUploads: React.Dispatch<React.SetStateAction<FileUploadState[]>>;
  uploadError: string | null;
  setUploadError: (v: string | null) => void;
  displayAttachedPipeline: { id: string; name: string } | null;
  setSelectedPipeline: (v: { id: string; name: string } | null) => void;
  alphafoldProgress: any;
  proteinmpnnProgress: any;
  handleAlphaFoldCancel: () => void;
  isCancellingAlphaFold: boolean;
  isQuickStartExpanded: boolean;
  setIsQuickStartExpanded: (v: boolean) => void;
  quickPrompts: string[];
  models: any[];
  textareaRef: React.RefObject<HTMLTextAreaElement>;
  handleSubmit: (e: React.FormEvent) => void;
  handleFileSelected: (file: File) => void;
  handleFilesSelected: (files: File[]) => void;
  handlePipelineSelect: () => void;
  handleServerFilesSelect: () => void;
  activeSessionId: string | null;
  setShowOpenFold2Dialog: (v: boolean) => void;
  setShowDiffDockDialog: (v: boolean) => void;
}

export const ChatInput: React.FC<ChatInputProps> = ({
  input,
  setInput,
  isLoading,
  showCenteredLayout,
  selections,
  removeSelection,
  clearSelections,
  formatSelection,
  fileUploads,
  setFileUploads,
  uploadError,
  setUploadError,
  displayAttachedPipeline,
  setSelectedPipeline,
  alphafoldProgress,
  proteinmpnnProgress,
  handleAlphaFoldCancel,
  isCancellingAlphaFold,
  isQuickStartExpanded,
  setIsQuickStartExpanded,
  quickPrompts,
  models,
  textareaRef,
  handleSubmit,
  handleFileSelected,
  handleFilesSelected,
  handlePipelineSelect,
  handleServerFilesSelect,
  activeSessionId,
  setShowOpenFold2Dialog,
  setShowDiffDockDialog,
}) => {
  return (
      <div className={`px-3 py-1.5 flex-shrink-0 ${!showCenteredLayout ? 'border-t border-gray-200' : ''}`}>
        {selections.length > 0 && (
          <div className="mb-1.5">
            <div className="flex items-center justify-between mb-1">
              <div className="text-[10px] text-gray-500 font-medium">
                Selected Residues ({selections.length})
              </div>
              {selections.length > 1 && (
                <button
                  onClick={clearSelections}
                  className="text-xs text-gray-500 hover:text-gray-700"
                >
                  Clear All
                </button>
              )}
            </div>
            <div className="flex flex-wrap gap-2">
              {selections.map((sel, index) => (
                <div 
                  key={index}
                  className="inline-flex items-center gap-1 bg-blue-100 text-blue-800 border border-blue-200 rounded-full px-3 py-1 text-xs font-medium"
                >
                  <span>{formatSelection(sel)}</span>
                  <button
                    onClick={() => removeSelection(index)}
                    className="ml-1 text-blue-600 hover:text-blue-800"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
        <ProgressTracker
          isVisible={alphafoldProgress.isVisible}
          onCancel={handleAlphaFoldCancel}
          isCancelling={isCancellingAlphaFold}
          cancelLabel="Cancel"
          className="mb-1.5"
          title={alphafoldProgress.title}
          eventName={alphafoldProgress.eventName}
        />
        <ProgressTracker
          isVisible={proteinmpnnProgress.isVisible}
          onCancel={proteinmpnnProgress.cancelProgress}
          className="mb-1.5"
          title={proteinmpnnProgress.title}
          eventName={proteinmpnnProgress.eventName}
        />

        {!showCenteredLayout && (
          <div className="mb-1.5">
            <button
              onClick={() => setIsQuickStartExpanded(!isQuickStartExpanded)}
              className="flex items-center justify-between w-full text-[10px] text-gray-500 hover:text-gray-700 transition-colors mb-1"
            >
              <span>Quick start:</span>
              {isQuickStartExpanded ? (
                <ChevronUp className="w-2.5 h-2.5" />
              ) : (
                <ChevronDown className="w-2.5 h-2.5" />
              )}
            </button>
            <div
              className={`overflow-hidden transition-all duration-200 ease-in-out ${
                isQuickStartExpanded ? 'max-h-24 opacity-100' : 'max-h-0 opacity-0'
              }`}
            >
              <div className="flex flex-wrap gap-1">
                {quickPrompts.map((prompt, index) => (
                  <button
                    key={index}
                    onClick={() => setInput(prompt)}
                    className="text-[10px] bg-gray-100 hover:bg-gray-200 text-gray-700 px-1.5 py-0.5 rounded transition-colors"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        <form onSubmit={handleSubmit} className={`flex flex-col gap-2 ${showCenteredLayout ? 'max-w-2xl w-full mx-auto' : ''}`}>
          {fileUploads.length > 0 && (
            <div className="flex items-center space-x-1.5 px-2 py-1 bg-blue-50 border border-blue-200 rounded-lg flex-wrap gap-1.5 mb-1.5">
              {fileUploads.map((fileState, index) => {
                const isUploading = fileState.status === 'uploading';
                const isUploaded = fileState.status === 'uploaded';
                const isError = fileState.status === 'error';
                
                return (
                  <div 
                    key={index} 
                    className={`flex items-center space-x-1 px-2 py-1 rounded-md border ${
                      isUploading 
                        ? 'bg-yellow-50 border-yellow-300' 
                        : isUploaded 
                        ? 'bg-green-50 border-green-300' 
                        : isError
                        ? 'bg-red-50 border-red-300'
                        : 'bg-white border-blue-200'
                    }`}
                  >
                    {isUploading && (
                      <div className="w-3 h-3 border-2 border-blue-600 border-t-transparent rounded-full animate-spin mr-1"></div>
                    )}
                    {isUploaded && (
                      <span className="text-green-600 mr-1">✓</span>
                    )}
                    {isError && (
                      <span className="text-red-600 mr-1">✗</span>
                    )}
                    <span 
                      className={`text-xs truncate max-w-[200px] ${
                        isUploading 
                          ? 'text-yellow-700' 
                          : isUploaded 
                          ? 'text-green-700' 
                          : isError
                          ? 'text-red-700'
                          : 'text-blue-700'
                      }`} 
                      title={fileState.file.name}
                    >
                      📎 {fileState.file.name}
                    </span>
                    {isError && fileState.error && (
                      <span className="text-xs text-red-600 ml-1" title={fileState.error}>
                        ⚠
                      </span>
                    )}
                    <button
                      type="button"
                      onClick={() => {
                        setFileUploads(prev => prev.filter((_, i) => i !== index));
                        setUploadError(null);
                      }}
                      className={`p-0.5 rounded ml-1 ${
                        isUploading 
                          ? 'hover:bg-yellow-100' 
                          : isUploaded 
                          ? 'hover:bg-green-100' 
                          : isError
                          ? 'hover:bg-red-100'
                          : 'hover:bg-blue-100'
                      }`}
                      title="Remove file"
                    >
                      <X className={`w-3 h-3 ${
                        isUploading 
                          ? 'text-yellow-600' 
                          : isUploaded 
                          ? 'text-green-600' 
                          : isError
                          ? 'text-red-600'
                          : 'text-blue-600'
                      }`} />
                    </button>
                  </div>
                );
              })}
            </div>
          )}
          
          {uploadError && (
            <div className="px-2 py-1 bg-red-50 border border-red-200 rounded-lg mb-1.5">
              <p className="text-[10px] text-red-700">{uploadError}</p>
            </div>
          )}

          {displayAttachedPipeline && (
            <div className="flex items-center space-x-1.5 px-2 py-1 bg-purple-50 border border-purple-200 rounded-lg flex-wrap gap-1.5 mb-1.5">
              <div className="flex items-center space-x-1 px-2 py-1 rounded-md bg-purple-100 border border-purple-300">
                <span className="text-purple-600 mr-1">⚙️</span>
                <span className="text-xs text-purple-700 truncate max-w-[200px]" title={displayAttachedPipeline.name}>
                  {displayAttachedPipeline.name}
                </span>
                <button
                  type="button"
                  onClick={() => setSelectedPipeline(null)}
                  className="p-0.5 rounded ml-1 hover:bg-purple-200"
                  title="Remove pipeline"
                >
                  <X className="w-3 h-3 text-purple-600" />
                </button>
              </div>
            </div>
          )}
          
          <div className="relative bg-white border border-gray-300 rounded-lg focus-within:ring-2 focus-within:ring-blue-500 focus-within:border-transparent">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={"Chat, visualize, or build..."}
              className={`w-full bg-transparent text-gray-900 focus:outline-none text-sm placeholder-gray-400 resize-none ${
                showCenteredLayout ? 'min-h-[120px] text-base' : 'min-h-[60px]'
              } px-2.5 pb-8 pt-2`}
              rows={showCenteredLayout ? 4 : 1}
              disabled={isLoading}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit(e as any);
                }
              }}
            />
            
            <div className="absolute bottom-0 left-0 right-0 flex items-center justify-between gap-1.5 px-2 py-1 border-t border-gray-100 bg-white rounded-b-lg z-10">
              <div className="flex items-center gap-2 flex-shrink-0">
                <AgentSelector />
                
                <ModelSelector
                  models={models}
                />
              </div>
              
              <div className="flex items-center gap-1 flex-shrink-0 ml-auto">
                <AttachmentMenu
                  onFileSelected={(file) => {
                    handleFileSelected(file);
                    setUploadError(null);
                  }}
                  onFilesSelected={(files) => {
                    handleFilesSelected(files);
                    setUploadError(null);
                  }}
                  onFileCleared={() => {
                    setFileUploads([]);
                    setUploadError(null);
                  }}
                  onError={(error) => {
                    setUploadError(error);
                    console.error('File upload error:', error);
                  }}
                  onPipelineSelect={handlePipelineSelect}
                  onServerFilesSelect={handleServerFilesSelect}
                  disabled={isLoading}
                  pendingFiles={fileUploads.map(f => f.file)}
                  sessionId={activeSessionId}
                />
                
                <button
                  type="button"
                  className="p-1.5 text-gray-400 hover:text-gray-600 transition-colors rounded-md hover:bg-gray-100"
                  title="Voice input"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                  </svg>
                </button>
                
                <button
                  type="submit"
                  disabled={!input.trim() || isLoading}
                  className="flex items-center justify-center p-1.5 text-gray-400 hover:text-gray-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed rounded-md hover:bg-gray-100"
                  title="Send"
                >
                  <Send className="w-5 h-5" />
                </button>
              </div>
            </div>
          </div>
        </form>

        {showCenteredLayout && (
          <div className="mt-4 max-w-2xl w-full mx-auto">
            <div className="flex flex-wrap gap-2 justify-center">
              {quickPrompts.map((prompt, index) => (
                <button
                  key={index}
                  onClick={() => setInput(prompt)}
                  className="px-4 py-2 bg-white hover:bg-gray-50 text-gray-700 rounded-lg border border-gray-200 text-sm font-medium transition-colors flex items-center space-x-2"
                >
                  <span>{prompt}</span>
                </button>
              ))}
              <button
                onClick={() => setShowOpenFold2Dialog(true)}
                className="px-4 py-2 bg-amber-50 hover:bg-amber-100 text-amber-800 rounded-lg border border-amber-200 text-sm font-medium transition-colors"
                title="OpenFold2 structure prediction"
              >
                OpenFold2
              </button>
              <button
                onClick={() => setShowDiffDockDialog(true)}
                className="px-4 py-2 bg-teal-50 hover:bg-teal-100 text-teal-800 rounded-lg border border-teal-200 text-sm font-medium transition-colors"
                title="DiffDock protein-ligand docking"
              >
                DiffDock
              </button>
              <button
                onClick={() => {}}
                className="px-4 py-2 bg-white hover:bg-gray-50 text-gray-700 rounded-lg border border-gray-200 text-sm font-medium transition-colors"
              >
                More
              </button>
            </div>
          </div>
        )}
      </div>
  );
};
