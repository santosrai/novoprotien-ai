import React, { useState } from 'react';
import { X, Search, Plus, Trash2, Download, Upload, Star, MoreVertical } from 'lucide-react';
import { useChatHistoryStore, useSessionManagement } from '../stores/chatHistoryStore';
import { SessionListItem } from './SessionListItem';

interface ChatHistoryPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

export const ChatHistoryPanel: React.FC<ChatHistoryPanelProps> = ({ isOpen, onClose }) => {
  const {
    searchQuery,
    setSearchQuery,
    selectedSessionIds,
    clearSelection,
    selectAllSessions,
    deleteSessions,
    getFilteredSessions,
    exportSessions,
    importSessions,
    getStorageStats,
    clearAllSessions,
  } = useChatHistoryStore();
  
  const { createSession } = useSessionManagement();
  const [showBulkActions, setShowBulkActions] = useState(false);

  if (!isOpen) return null;

  const filteredSessions = getFilteredSessions();
  const { totalSessions, totalMessages, estimatedSize } = getStorageStats();
  const hasSelections = selectedSessionIds.length > 0;

  const handleNewChat = () => {
    createSession();
    onClose();
  };

  const handleExportSelected = () => {
    const data = exportSessions(selectedSessionIds);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `chat-sessions-${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    clearSelection();
  };

  const handleExportAll = () => {
    const data = exportSessions();
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `all-chat-sessions-${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleImport = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      const content = e.target?.result as string;
      const success = importSessions(content);
      if (success) {
        alert('Chat sessions imported successfully!');
      } else {
        alert('Failed to import chat sessions. Please check the file format.');
      }
    };
    reader.readAsText(file);
    event.target.value = ''; // Reset file input
  };

  const handleDeleteSelected = () => {
    if (confirm(`Delete ${selectedSessionIds.length} selected chat session(s)? This cannot be undone.`)) {
      deleteSessions(selectedSessionIds);
    }
  };

  const handleClearAll = () => {
    if (confirm('Delete ALL chat sessions? This cannot be undone.')) {
      clearAllSessions();
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200">
          <div>
            <h2 className="text-xl font-semibold text-gray-900">Chat History</h2>
            <p className="text-sm text-gray-500">
              {totalSessions} sessions • {totalMessages} messages • {estimatedSize}
            </p>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setShowBulkActions(!showBulkActions)}
              className="p-2 text-gray-400 hover:text-gray-600 transition-colors"
              title="Bulk Actions"
            >
              <MoreVertical className="w-5 h-5" />
            </button>
            <button
              onClick={onClose}
              className="p-2 text-gray-400 hover:text-gray-600 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Bulk Actions Bar */}
        {showBulkActions && (
          <div className="p-3 bg-gray-50 border-b border-gray-200">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <button
                  onClick={selectAllSessions}
                  className="text-xs text-blue-600 hover:text-blue-800"
                >
                  Select All
                </button>
                <span className="text-gray-300">|</span>
                <button
                  onClick={clearSelection}
                  className="text-xs text-gray-600 hover:text-gray-800"
                >
                  Clear Selection
                </button>
                {hasSelections && (
                  <span className="text-xs text-gray-500">
                    {selectedSessionIds.length} selected
                  </span>
                )}
              </div>
              <div className="flex items-center space-x-2">
                <button
                  onClick={handleExportAll}
                  className="flex items-center space-x-1 px-2 py-1 text-xs text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded"
                >
                  <Download className="w-3 h-3" />
                  <span>Export All</span>
                </button>
                <label className="flex items-center space-x-1 px-2 py-1 text-xs text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded cursor-pointer">
                  <Upload className="w-3 h-3" />
                  <span>Import</span>
                  <input
                    type="file"
                    accept=".json"
                    onChange={handleImport}
                    className="hidden"
                  />
                </label>
                <button
                  onClick={handleClearAll}
                  className="flex items-center space-x-1 px-2 py-1 text-xs text-red-600 hover:text-red-800 hover:bg-red-50 rounded"
                >
                  <Trash2 className="w-3 h-3" />
                  <span>Clear All</span>
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Selected Actions Bar */}
        {hasSelections && (
          <div className="p-3 bg-blue-50 border-b border-blue-200">
            <div className="flex items-center justify-between">
              <span className="text-sm text-blue-800">
                {selectedSessionIds.length} session(s) selected
              </span>
              <div className="flex items-center space-x-2">
                <button
                  onClick={handleExportSelected}
                  className="flex items-center space-x-1 px-3 py-1 text-sm text-blue-600 hover:text-blue-800 hover:bg-blue-100 rounded"
                >
                  <Download className="w-4 h-4" />
                  <span>Export Selected</span>
                </button>
                <button
                  onClick={handleDeleteSelected}
                  className="flex items-center space-x-1 px-3 py-1 text-sm text-red-600 hover:text-red-800 hover:bg-red-100 rounded"
                >
                  <Trash2 className="w-4 h-4" />
                  <span>Delete Selected</span>
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Search and New Chat */}
        <div className="p-4 border-b border-gray-200">
          <div className="flex items-center space-x-3">
            <div className="flex-1 relative">
              <Search className="w-4 h-4 absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search chat history..."
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
              />
            </div>
            <button
              onClick={handleNewChat}
              className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
            >
              <Plus className="w-4 h-4" />
              <span>New Chat</span>
            </button>
          </div>
        </div>

        {/* Session List */}
        <div className="flex-1 overflow-y-auto">
          {filteredSessions.length === 0 ? (
            <div className="p-8 text-center">
              <div className="text-gray-400 mb-2">
                <Star className="w-12 h-12 mx-auto" />
              </div>
              <h3 className="text-lg font-medium text-gray-900 mb-1">
                {searchQuery ? 'No matching conversations' : 'No chat history yet'}
              </h3>
              <p className="text-gray-500 text-sm">
                {searchQuery 
                  ? 'Try adjusting your search terms'
                  : 'Start a new conversation to see it appear here'
                }
              </p>
              {!searchQuery && (
                <button
                  onClick={handleNewChat}
                  className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
                >
                  Start New Chat
                </button>
              )}
            </div>
          ) : (
            <div className="divide-y divide-gray-200">
              {filteredSessions.map((session) => (
                <SessionListItem
                  key={session.id}
                  session={session}
                  onSelect={() => onClose()}
                />
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-gray-200 bg-gray-50">
          <div className="flex items-center justify-between">
            <div className="text-xs text-gray-500">
              Storage: {estimatedSize} used • Auto-saved to browser
            </div>
            <div className="flex items-center space-x-3">
              <button
                onClick={clearSelection}
                disabled={!hasSelections}
                className="text-xs text-gray-600 hover:text-gray-800 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Clear Selection
              </button>
              <button
                onClick={onClose}
                className="px-3 py-1 text-sm text-gray-600 hover:text-gray-800 font-medium"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};