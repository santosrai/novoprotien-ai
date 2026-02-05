import React, { useState, useRef, useEffect } from 'react';
import { 
  Menu, 
  X, 
  Search, 
  Plus, 
  MessageSquare, 
  ChevronRight,
  Settings,
  Download,
  Trash2
} from 'lucide-react';
import { useChatHistoryStore, useSessionManagement } from '../stores/chatHistoryStore';
import { ChatHistoryItem } from './ChatHistoryItem';
import { useAppStore } from '../stores/appStore';

export const ChatHistorySidebar: React.FC = () => {
  const {
    activeSessionId,
    isSidebarCollapsed,
    searchQuery,
    selectedSessionIds,
    getFilteredSessions,
    toggleSidebar,
    setSearchQuery,
    clearSelection,
    exportSessions,
    deleteSessions,
    getStorageStats,
    saveViewerVisibility,
  } = useChatHistoryStore();

  const { createSession } = useSessionManagement();
  const { setViewerVisible, setActivePane } = useAppStore();
  const [showBulkActions, setShowBulkActions] = useState(false);
  const searchInputRef = useRef<HTMLInputElement>(null);

  const filteredSessions = getFilteredSessions();
  const { totalSessions } = getStorageStats();
  const hasSelections = selectedSessionIds.length > 0;
  
  // Check if we're on mobile
  const [isMobile, setIsMobile] = useState(false);
  
  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768);
    };
    
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  // Auto-focus search when sidebar expands
  useEffect(() => {
    if (!isSidebarCollapsed && searchInputRef.current) {
      setTimeout(() => searchInputRef.current?.focus(), 300);
    }
  }, [isSidebarCollapsed]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl/Cmd + B to toggle sidebar
      if ((e.ctrlKey || e.metaKey) && e.key === 'b') {
        e.preventDefault();
        toggleSidebar();
      }
      
      // Ctrl/Cmd + N to create new chat (when sidebar is open)
      if ((e.ctrlKey || e.metaKey) && e.key === 'n' && !isSidebarCollapsed) {
        e.preventDefault();
        handleNewChat();
      }

      // Escape to clear search
      if (e.key === 'Escape' && searchQuery && !isSidebarCollapsed) {
        e.preventDefault();
        setSearchQuery('');
        searchInputRef.current?.focus();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [toggleSidebar, isSidebarCollapsed, searchQuery, setSearchQuery]);

  const handleNewChat = async () => {
    const newSessionId = await createSession();
    setSearchQuery(''); // Clear search when creating new chat
    setViewerVisible(false); // Hide 3D visual editor when starting new chat
    setActivePane(null); // Hide all panes for new chat
    // Save visibility state to new session
    if (newSessionId) {
      saveViewerVisibility(newSessionId, false);
    }
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
    setShowBulkActions(false);
  };

  const handleDeleteSelected = () => {
    if (confirm(`Delete ${selectedSessionIds.length} selected chat session(s)? This cannot be undone.`)) {
      deleteSessions(selectedSessionIds);
      setShowBulkActions(false);
    }
  };

  // Collapsed sidebar view
  if (isSidebarCollapsed) {
    return (
      <div className="w-12 bg-white border-r border-gray-200 flex flex-col items-center py-2 space-y-2 flex-shrink-0">
        {/* Toggle button */}
        <button
          onClick={toggleSidebar}
          className="w-8 h-8 flex items-center justify-center text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded transition-colors"
          title="Expand sidebar (Ctrl+B)"
        >
          <Menu className="w-5 h-5" />
        </button>

        {/* New chat button */}
        <button
          onClick={handleNewChat}
          className="w-8 h-8 flex items-center justify-center text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded transition-colors"
          title="New chat (Ctrl+N)"
        >
          <Plus className="w-4 h-4" />
        </button>

        {/* Active chat indicator */}
        {activeSessionId && (
          <div className="w-8 h-8 flex items-center justify-center">
            <div className="w-2 h-2 bg-blue-500 rounded-full" title="Active chat" />
          </div>
        )}

        {/* Session count indicator */}
        {totalSessions > 0 && (
          <div className="mt-auto mb-2">
            <div className="w-6 h-6 bg-gray-100 border border-gray-200 rounded text-xs text-gray-700 flex items-center justify-center">
              {totalSessions > 99 ? '99+' : totalSessions}
            </div>
          </div>
        )}
      </div>
    );
  }

  // Expanded sidebar view
  return (
    <>
      {/* Mobile overlay */}
      {isMobile && !isSidebarCollapsed && (
        <div 
          className="fixed inset-0 bg-black bg-opacity-50 z-40 md:hidden"
          onClick={toggleSidebar}
        />
      )}
      
      <div className={`w-64 bg-white border-r border-gray-200 text-gray-900 flex flex-col h-full flex-shrink-0 animate-in slide-in-from-left duration-300 ${
        isMobile ? 'fixed left-0 top-0 z-50 md:relative md:z-auto shadow-xl' : ''
      }`}>
      {/* Header */}
      <div className="p-3 border-b border-gray-200">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center space-x-2">
            <MessageSquare className="w-5 h-5 text-gray-600" />
            <span className="font-medium text-sm text-gray-900">Chat History</span>
          </div>
          <div className="flex items-center space-x-1">
            <button
              onClick={() => setShowBulkActions(!showBulkActions)}
              className="p-1 text-gray-500 hover:text-gray-900 hover:bg-gray-100 rounded transition-colors"
              title="Bulk actions"
            >
              <Settings className="w-4 h-4" />
            </button>
            <button
              onClick={toggleSidebar}
              className="p-1 text-gray-500 hover:text-gray-900 hover:bg-gray-100 rounded transition-colors"
              title="Collapse sidebar (Ctrl+B)"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* New Chat Button */}
        <button
          onClick={handleNewChat}
          className="w-full flex items-center space-x-2 px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors text-sm"
        >
          <Plus className="w-4 h-4" />
          <span>New Chat</span>
          <div className="ml-auto text-xs text-blue-100">Ctrl+N</div>
        </button>
      </div>

      {/* Search */}
      <div className="p-3 border-b border-gray-200">
        <div className="relative">
          <Search className="w-4 h-4 absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
          <input
            ref={searchInputRef}
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search conversations..."
            className="w-full pl-10 pr-4 py-2 bg-gray-50 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm placeholder-gray-400"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Bulk Actions Bar */}
      {showBulkActions && (
        <div className="p-3 bg-gray-50 border-b border-gray-200">
          <div className="flex items-center justify-between text-xs">
            <span className="text-gray-600">
              {hasSelections ? `${selectedSessionIds.length} selected` : 'Select conversations'}
            </span>
            <div className="flex items-center space-x-2">
              {hasSelections && (
                <>
                  <button
                    onClick={handleExportSelected}
                    className="flex items-center space-x-1 px-2 py-1 text-gray-600 hover:text-gray-900 hover:bg-gray-200 rounded"
                  >
                    <Download className="w-3 h-3" />
                    <span>Export</span>
                  </button>
                  <button
                    onClick={handleDeleteSelected}
                    className="flex items-center space-x-1 px-2 py-1 text-red-600 hover:text-red-700 hover:bg-red-50 rounded"
                  >
                    <Trash2 className="w-3 h-3" />
                    <span>Delete</span>
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Chat List */}
      <div className="flex-1 overflow-y-auto">
        {filteredSessions.length === 0 ? (
          <div className="p-6 text-center">
            <MessageSquare className="w-12 h-12 text-gray-400 mx-auto mb-3" />
            <h3 className="text-sm font-medium text-gray-700 mb-1">
              {searchQuery ? 'No matching conversations' : 'No conversations yet'}
            </h3>
            <p className="text-xs text-gray-500">
              {searchQuery 
                ? 'Try adjusting your search terms'
                : 'Start a new conversation to see it appear here'
              }
            </p>
            {!searchQuery && (
              <button
                onClick={handleNewChat}
                className="mt-3 px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded text-xs transition-colors"
              >
                Start New Chat
              </button>
            )}
          </div>
        ) : (
          <div className="py-2">
            {filteredSessions.map((session) => (
              <ChatHistoryItem
                key={session.id}
                session={session}
                isActive={session.id === activeSessionId}
                isSelected={selectedSessionIds.includes(session.id)}
                showBulkActions={showBulkActions}
              />
            ))}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-3 border-t border-gray-200">
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>{totalSessions} conversation{totalSessions !== 1 ? 's' : ''}</span>
          <div className="flex items-center space-x-1">
            <span>Ctrl+B</span>
            <ChevronRight className="w-3 h-3" />
          </div>
        </div>
      </div>
      </div>
    </>
  );
};