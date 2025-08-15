import React, { useEffect } from 'react';
import { Atom, Settings, HelpCircle, History } from 'lucide-react';
import { useSettingsStore } from '../stores/settingsStore';
import { useChatHistoryStore } from '../stores/chatHistoryStore';

export const Header: React.FC = () => {
  const { setSettingsDialogOpen } = useSettingsStore();
  const { setHistoryPanelOpen, getStorageStats } = useChatHistoryStore();
  
  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === ',') {
        e.preventDefault();
        setSettingsDialogOpen(true);
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'h') {
        e.preventDefault();
        setHistoryPanelOpen(true);
      }
    };
    
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [setSettingsDialogOpen, setHistoryPanelOpen]);
  
  return (
    <header className="bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between">
      <div className="flex items-center space-x-2">
        <Atom className="w-8 h-8 text-blue-600" />
        <h1 className="text-xl font-bold text-gray-900">NovoProtein AI</h1>
        <span className="text-sm text-gray-500">Molecular Visualization Platform</span>
      </div>
      
      <div className="flex items-center space-x-4">
        <button className="flex items-center space-x-1 px-3 py-1 text-sm text-gray-600 hover:text-gray-900">
          <HelpCircle className="w-4 h-4" />
          <span>Help</span>
        </button>
        <button 
          onClick={() => setHistoryPanelOpen(true)}
          className="flex items-center space-x-1 px-3 py-1 text-sm text-gray-600 hover:text-gray-900 transition-colors"
          title="Chat History (Ctrl+H)"
        >
          <History className="w-4 h-4" />
          <span>History</span>
          {(() => {
            const stats = getStorageStats();
            return stats.totalSessions > 0 ? (
              <span className="ml-1 inline-flex items-center justify-center px-1.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                {stats.totalSessions}
              </span>
            ) : null;
          })()}
        </button>
        <button 
          onClick={() => setSettingsDialogOpen(true)}
          className="flex items-center space-x-1 px-3 py-1 text-sm text-gray-600 hover:text-gray-900 transition-colors"
          title="Open Settings (Ctrl+,)"
        >
          <Settings className="w-4 h-4" />
          <span>Settings</span>
        </button>
      </div>
    </header>
  );
};