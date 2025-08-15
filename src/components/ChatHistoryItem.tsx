import React, { useState, useRef, useEffect } from 'react';
import { 
  MessageSquare, 
  Pin, 
  Edit2, 
  Trash2, 
  Copy, 
  MoreHorizontal, 
  Check, 
  X,
  Star,
  Clock,
  User,
  Bot,
  Code,
  Search
} from 'lucide-react';
import { ChatSession, useChatHistoryStore, useSessionManagement } from '../stores/chatHistoryStore';

interface ChatHistoryItemProps {
  session: ChatSession;
  isActive: boolean;
  isSelected: boolean;
  showBulkActions: boolean;
}

export const ChatHistoryItem: React.FC<ChatHistoryItemProps> = ({
  session,
  isActive,
  isSelected,
  showBulkActions,
}) => {
  const {
    switchToSession,
    toggleSessionSelection,
    setSidebarCollapsed,
  } = useChatHistoryStore();
  
  const { updateSessionTitle, starSession, duplicateSession, deleteSession } = useSessionManagement();
  
  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState(session.title);
  const [showActions, setShowActions] = useState(false);
  const [isHovered, setIsHovered] = useState(false);
  const editInputRef = useRef<HTMLInputElement>(null);

  const isStarred = session.metadata.starred;

  // Format relative time
  const formatRelativeTime = (date: Date | string) => {
    const dateObj = new Date(date);
    const now = new Date();
    const diffInMs = now.getTime() - dateObj.getTime();
    const diffInHours = diffInMs / (1000 * 60 * 60);
    const diffInDays = diffInHours / 24;

    if (diffInHours < 1) {
      const diffInMinutes = Math.floor(diffInMs / (1000 * 60));
      return diffInMinutes < 1 ? 'now' : `${diffInMinutes}m`;
    } else if (diffInHours < 24) {
      return `${Math.floor(diffInHours)}h`;
    } else if (diffInDays < 7) {
      return `${Math.floor(diffInDays)}d`;
    } else {
      return dateObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }
  };

  // Generate conversation type icon based on content
  const getConversationIcon = () => {
    const firstUserMessage = session.messages.find(m => m.type === 'user')?.content.toLowerCase() || '';
    
    if (firstUserMessage.includes('code') || firstUserMessage.includes('function') || firstUserMessage.includes('debug')) {
      return <Code className="w-4 h-4 text-green-400" />;
    } else if (firstUserMessage.includes('search') || firstUserMessage.includes('find')) {
      return <Search className="w-4 h-4 text-blue-400" />;
    } else if (firstUserMessage.includes('show') || firstUserMessage.includes('display') || firstUserMessage.includes('visualize')) {
      return <Bot className="w-4 h-4 text-purple-400" />;
    } else {
      return <MessageSquare className="w-4 h-4 text-gray-400" />;
    }
  };

  // Get user avatar/initials
  const getUserAvatar = () => {
    const initials = session.title.split(' ').slice(0, 2).map(word => word[0]).join('').toUpperCase();
    return (
      <div className="w-6 h-6 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center text-xs font-medium text-white">
        {initials.length > 0 ? initials : 'C'}
      </div>
    );
  };

  // Auto-focus edit input
  useEffect(() => {
    if (isEditing && editInputRef.current) {
      editInputRef.current.focus();
      editInputRef.current.select();
    }
  }, [isEditing]);

  const handleSelect = () => {
    if (showBulkActions) {
      toggleSessionSelection(session.id);
    } else {
      switchToSession(session.id);
      setSidebarCollapsed(false); // Ensure sidebar stays open when selecting
    }
  };

  const handleEditStart = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsEditing(true);
    setEditTitle(session.title);
    setShowActions(false);
  };

  const handleEditSave = () => {
    const trimmedTitle = editTitle.trim();
    if (trimmedTitle && trimmedTitle !== session.title) {
      updateSessionTitle(session.id, trimmedTitle);
    }
    setIsEditing(false);
  };

  const handleEditCancel = () => {
    setEditTitle(session.title);
    setIsEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleEditSave();
    } else if (e.key === 'Escape') {
      handleEditCancel();
    }
  };

  const handleToggleStar = (e: React.MouseEvent) => {
    e.stopPropagation();
    starSession(session.id, !isStarred);
    setShowActions(false);
  };

  const handleDuplicate = (e: React.MouseEvent) => {
    e.stopPropagation();
    duplicateSession(session.id);
    setShowActions(false);
  };

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm(`Delete "${session.title}"? This cannot be undone.`)) {
      deleteSession(session.id);
    }
    setShowActions(false);
  };


  return (
    <div
      className={`relative group px-3 py-2 mx-2 rounded-lg cursor-pointer transition-all duration-200 ${
        isActive 
          ? 'bg-blue-50 border border-blue-200' 
          : isSelected
          ? 'bg-blue-100 border border-blue-300'
          : isHovered
          ? 'bg-gray-50'
          : 'hover:bg-gray-50'
      }`}
      onClick={handleSelect}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => {
        setIsHovered(false);
        setShowActions(false);
      }}
    >
      <div className="flex items-start space-x-3">
        {/* Selection Checkbox (visible during bulk actions) */}
        {showBulkActions && (
          <div className="mt-1">
            <input
              type="checkbox"
              checked={isSelected}
              onChange={() => toggleSessionSelection(session.id)}
              className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500 bg-white"
              onClick={(e) => e.stopPropagation()}
            />
          </div>
        )}

        {/* Avatar/Icon */}
        <div className="flex-shrink-0 mt-0.5">
          {showBulkActions ? getConversationIcon() : getUserAvatar()}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          {/* Title */}
          <div className="flex items-center space-x-2 mb-1">
            {isEditing ? (
              <div className="flex items-center space-x-1 flex-1">
                <input
                  ref={editInputRef}
                  type="text"
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  onKeyDown={handleKeyDown}
                  className="flex-1 bg-white border border-gray-300 rounded px-2 py-1 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  onClick={(e) => e.stopPropagation()}
                />
                <button
                  onClick={(e) => { e.stopPropagation(); handleEditSave(); }}
                  className="p-1 text-green-600 hover:text-green-700"
                >
                  <Check className="w-3 h-3" />
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); handleEditCancel(); }}
                  className="p-1 text-red-600 hover:text-red-700"
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            ) : (
              <>
                <h3 className={`text-sm font-medium truncate flex-1 ${
                  isActive ? 'text-blue-700' : 'text-gray-700'
                }`}>
                  {session.title}
                </h3>
                
                {/* Star indicator */}
                {isStarred && (
                  <Star className="w-3 h-3 text-yellow-400 fill-current flex-shrink-0" />
                )}
                
                {/* Active indicator */}
                {isActive && (
                  <div className="w-2 h-2 bg-blue-500 rounded-full flex-shrink-0" />
                )}
              </>
            )}
          </div>

          {/* Metadata */}
          <div className="flex items-center justify-between text-xs text-gray-400">
            <div className="flex items-center space-x-2">
              <Clock className="w-3 h-3" />
              <span>{formatRelativeTime(session.lastModified)}</span>
              <span>•</span>
              <span>{session.metadata.messageCount} msg{session.metadata.messageCount !== 1 ? 's' : ''}</span>
            </div>
            
            {/* Message type indicators */}
            <div className="flex items-center space-x-1">
              {session.messages.some(m => m.type === 'user') && (
                <User className="w-3 h-3 text-blue-400" />
              )}
              {session.messages.some(m => m.type === 'ai') && (
                <Bot className="w-3 h-3 text-green-400" />
              )}
            </div>
          </div>
        </div>

        {/* Actions Menu */}
        {!showBulkActions && !isEditing && (isHovered || isActive) && (
          <div className="flex-shrink-0">
            <button
              onClick={(e) => {
                e.stopPropagation();
                setShowActions(!showActions);
              }}
              className="p-1 text-gray-400 hover:text-gray-600 rounded transition-colors"
            >
              <MoreHorizontal className="w-4 h-4" />
            </button>

            {showActions && (
              <div className="absolute right-2 top-8 w-40 bg-white border border-gray-200 rounded-lg shadow-xl z-20">
                <div className="py-1">
                  <button
                    onClick={handleEditStart}
                    className="w-full flex items-center space-x-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 hover:text-gray-900"
                  >
                    <Edit2 className="w-4 h-4" />
                    <span>Rename</span>
                  </button>
                  
                  <button
                    onClick={handleToggleStar}
                    className="w-full flex items-center space-x-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 hover:text-gray-900"
                  >
                    {isStarred ? (
                      <>
                        <Star className="w-4 h-4 text-yellow-400 fill-current" />
                        <span>Unpin</span>
                      </>
                    ) : (
                      <>
                        <Pin className="w-4 h-4" />
                        <span>Pin</span>
                      </>
                    )}
                  </button>
                  
                  <button
                    onClick={handleDuplicate}
                    className="w-full flex items-center space-x-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 hover:text-gray-900"
                  >
                    <Copy className="w-4 h-4" />
                    <span>Duplicate</span>
                  </button>
                  
                  <div className="border-t border-gray-200 my-1"></div>
                  
                  <button
                    onClick={handleDelete}
                    className="w-full flex items-center space-x-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50 hover:text-red-700"
                  >
                    <Trash2 className="w-4 h-4" />
                    <span>Delete</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Click outside to close actions menu */}
      {showActions && (
        <div
          className="fixed inset-0 z-10"
          onClick={() => setShowActions(false)}
        />
      )}
    </div>
  );
};