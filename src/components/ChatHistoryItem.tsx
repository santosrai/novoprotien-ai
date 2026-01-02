import React, { useState, useRef, useEffect } from 'react';
import { 
  Pin, 
  Edit2, 
  Trash2, 
  Copy, 
  MoreHorizontal, 
  Check, 
  X,
  Star
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
      switchToSession(session.id).catch(err => console.error('Failed to switch session:', err));
      setSidebarCollapsed(false); // Ensure sidebar stays open when selecting
    }
  };

  const handleEditStart = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsEditing(true);
    setEditTitle(session.title);
    setShowActions(false);
  };

  const handleEditSave = async () => {
    const trimmedTitle = editTitle.trim();
    if (trimmedTitle && trimmedTitle !== session.title) {
      await updateSessionTitle(session.id, trimmedTitle);
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

        {/* Content */}
        <div className="flex-1 min-w-0">
          {/* Title */}
          <div className="flex items-center space-x-2">
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
                <h3 className={`text-sm font-medium truncate flex-1 leading-tight ${
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