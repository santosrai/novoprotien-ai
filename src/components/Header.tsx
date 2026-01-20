import React, { useState } from 'react';
import { Atom, Box, Workflow, Menu, X, FolderOpen } from 'lucide-react';
import { useAppStore } from '../stores/appStore';
import { useChatHistoryStore } from '../stores/chatHistoryStore';
import { ProfileMenu } from './auth/ProfileMenu';
import { useHasCode } from '../utils/codeUtils';

export const Header: React.FC = () => {
  const { activePane, isViewerVisible, setViewerVisible, setActivePane } = useAppStore();
  const { activeSessionId, saveViewerVisibility } = useChatHistoryStore();
  const hasCode = useHasCode();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  
  const handleOpenPipeline = () => {
    setActivePane('pipeline' as any);
    setViewerVisible(true); // For chat panel layout
    setIsMobileMenuOpen(false);
  };
  
  const handleOpenFiles = () => {
    setActivePane('files' as any);
    setViewerVisible(true); // For chat panel layout
    setIsMobileMenuOpen(false);
  };
  
  const handleToggleViewer = () => {
    // Don't open viewer if there's no code or structure to display
    if (!hasCode && activePane !== 'viewer') {
      return; // Silently do nothing if there's no code
    }
    
    const currentPane = activePane;
    if (currentPane === 'viewer') {
      setActivePane('editor');
    } else if (currentPane === 'editor') {
      setActivePane('viewer');
    } else {
      // If pane is null or any other value, open viewer
      setActivePane('viewer');
    }
    // Update isViewerVisible for chat panel layout
    setViewerVisible(true);
    if (activeSessionId) {
      saveViewerVisibility(activeSessionId, true);
    }
    setIsMobileMenuOpen(false);
  };
  
  return (
    <header className="bg-white border-b border-gray-200 px-3 sm:px-4 py-2 sm:py-3 flex items-center justify-between relative">
      <div className="flex items-center space-x-2 min-w-0 flex-shrink">
        <Atom className="w-6 h-6 sm:w-8 sm:h-8 text-blue-600 flex-shrink-0" />
        <h1 className="text-lg sm:text-xl font-bold text-gray-900 truncate">NovoProtein AI</h1>
        <span className="hidden sm:inline text-sm text-gray-500">Molecular Visualization Platform</span>
      </div>
      
      {/* Desktop Menu */}
      <div className="hidden md:flex items-center space-x-2 lg:space-x-4">
        {/* 3D Visual Editor Button */}
        <button
          onClick={handleToggleViewer}
          className={`flex items-center space-x-1 px-2 lg:px-3 py-1 text-xs lg:text-sm transition-colors ${
            hasCode || activePane === 'viewer'
              ? 'text-gray-600 hover:text-gray-900'
              : 'text-gray-400 cursor-not-allowed'
          }`}
          title={hasCode || activePane === 'viewer' ? 'Toggle 3D Visual Editor' : 'No structure loaded - generate or load a structure first'}
          disabled={!hasCode && activePane !== 'viewer'}
        >
          <Box className="w-4 h-4" />
          <span className="hidden lg:inline">3D Visual Editor</span>
        </button>
        
        {/* Pipeline Canvas Button */}
        <button
          onClick={handleOpenPipeline}
          className="flex items-center space-x-1 px-2 lg:px-3 py-1 text-xs lg:text-sm text-gray-600 hover:text-gray-900 transition-colors"
          title="Open Pipeline Canvas"
        >
          <Workflow className="w-4 h-4" />
          <span className="hidden lg:inline">Pipeline Canvas</span>
        </button>
        
        {/* File Explorer Button */}
        <button
          onClick={handleOpenFiles}
          className="flex items-center space-x-1 px-2 lg:px-3 py-1 text-xs lg:text-sm text-gray-600 hover:text-gray-900 transition-colors"
          title="Open File Explorer"
        >
          <FolderOpen className="w-4 h-4" />
          <span className="hidden lg:inline">Files</span>
        </button>
        
        <ProfileMenu />
      </div>

      {/* Mobile Menu Button */}
      <div className="md:hidden flex items-center space-x-2">
        <ProfileMenu />
        <button
          onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
          className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded transition-colors"
          aria-label="Toggle menu"
        >
          {isMobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {/* Mobile Menu Dropdown */}
      {isMobileMenuOpen && (
        <>
          <div 
            className="fixed inset-0 bg-black bg-opacity-50 z-40 md:hidden"
            onClick={() => setIsMobileMenuOpen(false)}
          />
          <div className="absolute top-full left-0 right-0 bg-white border-b border-gray-200 shadow-lg z-50 md:hidden">
            <div className="px-4 py-3 space-y-3">
              {/* 3D Visual Editor Button */}
              <button
                onClick={handleToggleViewer}
                className={`w-full flex items-center space-x-2 px-3 py-2 text-sm rounded transition-colors ${
                  hasCode || activePane === 'viewer'
                    ? 'text-gray-700 hover:bg-gray-50'
                    : 'text-gray-400 cursor-not-allowed'
                }`}
                title={hasCode || activePane === 'viewer' ? 'Toggle 3D Visual Editor' : 'No structure loaded - generate or load a structure first'}
                disabled={!hasCode && activePane !== 'viewer'}
              >
                <Box className="w-4 h-4" />
                <span>3D Visual Editor</span>
              </button>
              
              {/* Pipeline Canvas Button */}
              <button
                onClick={handleOpenPipeline}
                className="w-full flex items-center space-x-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 rounded transition-colors"
              >
                <Workflow className="w-4 h-4" />
                <span>Pipeline Canvas</span>
              </button>
              
              {/* File Explorer Button */}
              <button
                onClick={handleOpenFiles}
                className="w-full flex items-center space-x-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 rounded transition-colors"
              >
                <FolderOpen className="w-4 h-4" />
                <span>Files</span>
              </button>
            </div>
          </div>
        </>
      )}
    </header>
  );
};