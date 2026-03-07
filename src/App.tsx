import { Header } from './components/Header';
import { ChatPanel } from './components/ChatPanel';
import { CodeEditor } from './components/CodeEditor';
import { SettingsDialog } from './components/SettingsDialog';
import { ChatHistoryPanel } from './components/ChatHistoryPanel';
import { ChatHistorySidebar } from './components/ChatHistorySidebar';
import { ResizablePanel } from './components/ResizablePanel';
import { ErrorDashboard, useErrorDashboard } from './components/ErrorDashboard';
import { FileBrowser } from './components/FileBrowser';
import { FileEditor } from './components/FileEditor';
import { MolstarSkeleton } from './components/MolstarSkeleton';
import { PipelineCanvas, PipelineManager, PipelineExecution, PipelineThemeWrapper, PipelineProvider } from './components/pipeline-canvas';
import { api, getAuthHeaders } from './utils/api';
import { useAuthStore } from './stores/authStore';
import { useTheme } from './contexts/ThemeContext';
import { useAppStore } from './stores/appStore';
import { useSettingsStore } from './stores/settingsStore';
import { useChatHistoryStore } from './stores/chatHistoryStore';
import { useEffect, useState, useCallback, Suspense, lazy, useMemo } from 'react';
import { MobileSegmentedControl, MobileTab } from './components/MobileSegmentedControl';

// Lazy load MolstarViewer - only load when viewer is visible
const MolstarViewer = lazy(() => import('./components/MolstarViewer').then(module => ({ default: module.MolstarViewer })));

function App() {
  const { activePane, setActivePane, chatPanelWidth, setChatPanelWidth, isViewerVisible, selectedFile, setSelectedFile } = useAppStore();
  const { settings, isSettingsDialogOpen, setSettingsDialogOpen } = useSettingsStore();
  const { isHistoryPanelOpen, setHistoryPanelOpen } = useChatHistoryStore();
  const [isPipelineManagerOpen, setIsPipelineManagerOpen] = useState(false);
  const user = useAuthStore((state) => state.user);
  const errorDashboard = useErrorDashboard();
  const { theme } = useTheme();

  // Mobile state
  const [isMobile, setIsMobile] = useState(() => window.innerWidth < 768);
  const [mobileActiveTab, setMobileActiveTab] = useState<MobileTab>('chat');

  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  // Auto-switch mobile tab when viewer/pane becomes active
  useEffect(() => {
    if (!isMobile) return;
    if (isViewerVisible && activePane) {
      const paneToTab: Record<string, MobileTab> = {
        viewer: 'viewer',
        editor: 'viewer',
        pipeline: 'pipeline',
        files: 'files',
      };
      const tab = paneToTab[activePane];
      if (tab) setMobileActiveTab(tab);
    }
  }, [isMobile, isViewerVisible, activePane]);

  const handleMobileTabChange = useCallback((tab: MobileTab) => {
    setMobileActiveTab(tab);
    if (tab === 'chat') return; // chat doesn't change activePane
    if (tab === 'viewer') {
      setActivePane('viewer');
      if (!isViewerVisible) {
        // Ensure viewer is visible when switching to viewer tab
        useAppStore.getState().setViewerVisible(true);
      }
    } else if (tab === 'pipeline') {
      setActivePane('pipeline');
      if (!isViewerVisible) useAppStore.getState().setViewerVisible(true);
    } else if (tab === 'files') {
      setActivePane('files');
      if (!isViewerVisible) useAppStore.getState().setViewerVisible(true);
    }
  }, [setActivePane, isViewerVisible]);

  // Listen for pipeline manager open event
  useEffect(() => {
    const handleOpenPipelineManager = () => {
      setIsPipelineManagerOpen(true);
    };
    window.addEventListener('open-pipeline-manager', handleOpenPipelineManager);
    return () => window.removeEventListener('open-pipeline-manager', handleOpenPipelineManager);
  }, []);
  
  // Auto-switch to viewer when editor gets disabled
  useEffect(() => {
    if (!settings.codeEditor.enabled && activePane === 'editor') {
      setActivePane('viewer');
    }
  }, [settings.codeEditor.enabled, activePane, setActivePane]);

  const handleFileSelect = async (file: any) => {
    // Load file content and show in editor
    try {
      console.log('[App] Loading file:', file.file_id, 'type:', file.type);
      
      // Use the generic file content endpoint for all file types
      const response = await api.get(`/files/${file.file_id}`);
      
      if (response.data.status === 'success') {
        console.log('[App] File loaded successfully:', response.data.filename);
        setSelectedFile({
          id: file.file_id,
          type: file.type,
          content: response.data.content,
          filename: file.filename || response.data.filename || `file_${file.file_id}.pdb`,
        } as { id: string; type: string; content: string; filename?: string });
        setActivePane('files');
      } else {
        console.error('[App] Failed to load file - unexpected response:', response.data);
        alert('Failed to load file: Unexpected response format');
      }
    } catch (error: any) {
      console.error('[App] Failed to load file:', error);
      if (error.response) {
        console.error('[App] Error response:', error.response.status, error.response.data);
        if (error.response.status === 404) {
          alert(`File not found. It may have been deleted or you don't have access to it.`);
        } else {
          alert(`Failed to load file: ${error.response.data?.detail || error.response.data?.error || 'Unknown error'}`);
        }
      } else {
        alert(`Failed to load file: ${error.message || 'Unknown error'}`);
      }
    }
  };

  const handleCloseFile = () => {
    setSelectedFile(null);
    setActivePane('viewer');
  };

  // Memoize authState to prevent PipelineProvider from re-syncing on every render
  const authState = useMemo(
    () => ({ user: user ?? null, isAuthenticated: !!user }),
    [user?.id]
  );

  // Mark App as ready for test detection
  useEffect(() => {
    const timer = setTimeout(() => {
      document.body.setAttribute('data-app-ready', 'true');
    }, 500);
    return () => clearTimeout(timer);
  }, []);

  return (
    <PipelineProvider
      apiClient={api}
      authState={authState}
      getAuthHeaders={getAuthHeaders}
    >
      <div className="h-screen flex flex-col bg-app text-app" data-testid="app-container" data-app-ready="true">
        <Header />
      
      {/* Mobile segmented control */}
      {isMobile && <MobileSegmentedControl activeTab={mobileActiveTab} onTabChange={handleMobileTabChange} />}

      {isMobile ? (
        /* ── Mobile layout ── */
        <div className="flex-1 flex flex-row min-h-0 overflow-hidden" style={{ paddingBottom: 'env(safe-area-inset-bottom, 0px)' }}>
          {/* Sidebar — collapsed bar on mobile */}
          <ChatHistorySidebar />

          {/* Chat panel — always mounted, hidden via CSS */}
          <div className={`flex-1 flex flex-col min-h-0 overflow-hidden bg-white ${mobileActiveTab !== 'chat' ? 'hidden' : ''}`}>
            <ChatPanel />
          </div>

          {/* Right-side panes — viewer / pipeline / files */}
          <div className={`flex-1 flex flex-col min-w-0 ${mobileActiveTab === 'chat' ? 'hidden' : ''}`}>
            <div className="flex-1 min-h-0 relative">
              {/* Molstar viewer */}
              <div
                className="absolute inset-0 bg-gray-900"
                style={{
                  display: mobileActiveTab === 'viewer' ? 'block' : 'none',
                  visibility: mobileActiveTab === 'viewer' ? 'visible' : 'hidden',
                  zIndex: mobileActiveTab === 'viewer' ? 1 : 0,
                }}
              >
                <Suspense fallback={<MolstarSkeleton message="Loading molecular viewer..." />}>
                  <MolstarViewer />
                </Suspense>
              </div>

              {/* Pipeline */}
              {mobileActiveTab === 'pipeline' && (
                <div className="absolute inset-0 z-10">
                  <PipelineThemeWrapper externalTheme={theme} className="h-full">
                    <PipelineCanvas />
                  </PipelineThemeWrapper>
                </div>
              )}

              {/* Files */}
              {mobileActiveTab === 'files' && (
                <div className="absolute inset-0 z-10">
                  {selectedFile ? (
                    <FileEditor
                      fileId={selectedFile.id}
                      filename={selectedFile.filename || `file_${selectedFile.id}.pdb`}
                      fileType={selectedFile.type}
                      onClose={handleCloseFile}
                    />
                  ) : (
                    <FileBrowser onFileSelect={handleFileSelect} />
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      ) : (
        /* ── Desktop layout (unchanged) ── */
        <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
          <ChatHistorySidebar />

          {isViewerVisible ? (
            <ResizablePanel
              defaultWidth={chatPanelWidth}
              minWidth={280}
              maxWidth={600}
              position="left"
              onWidthChange={setChatPanelWidth}
              className="bg-white"
            >
              <ChatPanel />
            </ResizablePanel>
          ) : (
            <div className="flex-1 bg-white flex flex-col min-h-0 overflow-hidden">
              <ChatPanel />
            </div>
          )}

          {(activePane === 'viewer' || activePane === 'editor' || activePane === 'files' || activePane === 'pipeline') && (
            <div className="flex-1 flex flex-col min-w-0">
              <div className="flex-1 min-h-0 relative">
                <div
                  className="absolute inset-0 bg-gray-900"
                  style={{
                    display: (activePane === 'viewer' || activePane === 'editor') ? 'block' : 'none',
                    visibility: activePane === 'viewer' ? 'visible' : 'hidden',
                    zIndex: activePane === 'viewer' ? 1 : 0,
                  }}
                >
                  <Suspense fallback={<MolstarSkeleton message="Loading molecular viewer..." />}>
                    <MolstarViewer />
                  </Suspense>
                </div>

                {activePane === 'editor' && settings.codeEditor.enabled && (
                  <div className="absolute inset-0 z-10">
                    <CodeEditor />
                  </div>
                )}

                {activePane === 'pipeline' && (
                  <div className="absolute inset-0 z-10">
                    <PipelineThemeWrapper externalTheme={theme} className="h-full">
                      <PipelineCanvas />
                    </PipelineThemeWrapper>
                  </div>
                )}

                {activePane === 'files' && (
                  <div className="absolute inset-0 z-10">
                    {selectedFile ? (
                      <FileEditor
                        fileId={selectedFile.id}
                        filename={selectedFile.filename || `file_${selectedFile.id}.pdb`}
                        fileType={selectedFile.type}
                        onClose={handleCloseFile}
                      />
                    ) : (
                      <FileBrowser onFileSelect={handleFileSelect} />
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
      
      {/* Settings Dialog */}
      <SettingsDialog 
        isOpen={isSettingsDialogOpen}
        onClose={() => setSettingsDialogOpen(false)}
      />
      
      {/* Chat History Panel */}
      <ChatHistoryPanel 
        isOpen={isHistoryPanelOpen}
        onClose={() => setHistoryPanelOpen(false)}
      />

      {/* Error Dashboard (Ctrl+Shift+E to open) */}
      <ErrorDashboard 
        isOpen={errorDashboard.isOpen} 
        onClose={errorDashboard.closeDashboard} 
      />

      {/* Pipeline Manager Modal */}
      <PipelineManager
        isOpen={isPipelineManagerOpen}
        onClose={() => setIsPipelineManagerOpen(false)}
      />

      {/* Pipeline Execution Monitor */}
      <PipelineExecution apiClient={api} />
      </div>
    </PipelineProvider>
  );
}

export default App;