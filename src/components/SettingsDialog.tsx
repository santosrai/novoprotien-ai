import React, { useState } from 'react';
import { X, Code2, Palette, Zap, RotateCcw, History, Settings, Sun, Moon, ExternalLink } from 'lucide-react';
import { useSettingsStore } from '../stores/settingsStore';
import { useChatHistoryStore } from '../stores/chatHistoryStore';
import { useTheme } from '../contexts/ThemeContext';

interface SettingsDialogProps {
  isOpen: boolean;
  onClose: () => void;
}

export const SettingsDialog: React.FC<SettingsDialogProps> = ({ isOpen, onClose }) => {
  const { settings, updateSettings, resetSettings } = useSettingsStore();
  const { getStorageStats, cleanupOldSessions, clearAllSessions, exportSessions } = useChatHistoryStore();
  const { theme, setTheme } = useTheme();
  const [activeTab, setActiveTab] = useState<'editor' | 'interface' | 'api' | 'chat-history' | 'advanced'>('editor');
  const [localSettings, setLocalSettings] = useState(settings);

  // Sync localSettings when dialog opens or settings change
  React.useEffect(() => {
    if (isOpen) {
      // Ensure api and langsmith fields exist
      const settingsWithApi = {
        ...settings,
        api: settings.api || { key: '' },
        langsmith: settings.langsmith || { enabled: false, apiKey: '', project: 'novoprotein-agent' }
      };
      setLocalSettings(settingsWithApi);
    }
  }, [isOpen, settings]);
  if (!isOpen) return null;

  const handleSettingChange = (path: string, value: any) => {
    const newSettings = { ...localSettings };
    const keys = path.split('.');
    let current = newSettings as any;

    for (let i = 0; i < keys.length - 1; i++) {
      current = current[keys[i]];
    }
    current[keys[keys.length - 1]] = value;

    setLocalSettings(newSettings);
    // Save settings immediately when changed
    updateSettings(newSettings);
  };

  const handleCancel = () => {
    setLocalSettings(settings);
    onClose();
  };

  const handleReset = () => {
    if (confirm('Reset all settings to default values? This cannot be undone.')) {
      resetSettings();
      setLocalSettings(settings);
    }
  };

  const Tab = ({ id, icon: Icon, label }: { id: typeof activeTab; icon: any; label: string }) => (
    <button
      onClick={() => setActiveTab(id)}
      className={`flex items-center space-x-2 px-3 sm:px-4 py-2 rounded-lg font-medium text-xs sm:text-sm transition-colors whitespace-nowrap ${activeTab === id
        ? 'bg-blue-600 !text-white shadow-lg'
        : 'text-gray-800 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200 hover:bg-gray-50 dark:hover:bg-slate-700/50'
        }`}
      style={activeTab === id ? { color: '#ffffff' } : undefined}
    >
      <Icon className={`w-4 h-4 ${activeTab === id ? '!text-white' : ''}`} style={activeTab === id ? { color: '#ffffff' } : undefined} />
      <span className={activeTab === id ? '!text-white' : ''} style={activeTab === id ? { color: '#ffffff' } : undefined}>{label}</span>
    </button>
  );

  const Switch = ({ checked, onChange, label, description }: {
    checked: boolean;
    onChange: (checked: boolean) => void;
    label: string;
    description?: string;
  }) => (
    <div className="flex items-start justify-between py-3">
      <div className="flex-1">
        <div className="font-medium text-gray-900 dark:text-gray-100 text-sm">{label}</div>
        {description && <div className="text-gray-600 dark:text-gray-400 text-xs mt-1">{description}</div>}
      </div>
      <button
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 dark:focus:ring-offset-slate-800 ${checked ? 'bg-blue-600' : 'bg-gray-200 dark:bg-slate-600'
          }`}
      >
        <span
          className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${checked ? 'translate-x-6' : 'translate-x-1'
            }`}
        />
      </button>
    </div>
  );

  const Select = ({ value, onChange, options, label, description }: {
    value: string | number;
    onChange: (value: string | number) => void;
    options: { value: string | number; label: string }[];
    label: string;
    description?: string;
  }) => (
    <div className="py-3">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="font-medium text-gray-900 dark:text-gray-100 text-sm">{label}</div>
          {description && <div className="text-gray-600 dark:text-gray-400 text-xs mt-1">{description}</div>}
        </div>
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="ml-4 px-3 py-1 border border-gray-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        >
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>
    </div>
  );

  return (
    <div className="fixed inset-0 bg-black/50 dark:bg-black/70 flex items-center justify-center p-2 sm:p-4 z-50">
      <div 
        className="bg-white dark:bg-slate-800 rounded-lg shadow-xl w-full max-w-2xl max-h-[95vh] sm:max-h-[90vh] overflow-hidden settings-dialog-content flex flex-col"
        style={{
          backgroundColor: theme === 'dark' ? '#1e293b' : '#ffffff',
          opacity: 1,
        }}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 sm:p-6 border-b border-gray-200 dark:border-slate-700 flex-shrink-0">
          <h2 className="text-lg sm:text-xl font-semibold text-gray-900 dark:text-gray-100">Settings</h2>
          <button
            onClick={handleCancel}
            className="text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
          >
            <X className="w-5 h-5 sm:w-6 sm:h-6" />
          </button>
        </div>

        <div className="flex flex-col sm:flex-row flex-1 min-h-0 overflow-hidden">
          {/* Sidebar */}
          <div className="w-full sm:w-48 bg-white dark:bg-white border-b sm:border-b-0 sm:border-r border-gray-200 dark:border-slate-700 p-3 sm:p-4 flex-shrink-0">
            <div className="flex sm:flex-col space-x-2 sm:space-x-0 sm:space-y-2 overflow-x-auto sm:overflow-x-visible">
              <Tab id="editor" icon={Code2} label="Editor" />
              <Tab id="interface" icon={Palette} label="Interface" />
              <Tab id="api" icon={Zap} label="API Keys" />
              <Tab id="chat-history" icon={History} label="Chat History" />
              <Tab id="advanced" icon={Settings} label="Advanced" />
            </div>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto min-h-0">
            <div className="p-4 sm:p-6">
              {activeTab === 'editor' && (
                <div className="space-y-1">
                  <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-4">Code Editor Settings</h3>

                  <Switch
                    checked={localSettings.codeEditor.enabled}
                    onChange={(checked) => handleSettingChange('codeEditor.enabled', checked)}
                    label="Show Code Editor"
                    description="Display the code editor panel alongside the molecular viewer"
                  />

                  <div className="border-t border-gray-200 pt-1">
                    <Switch
                      checked={localSettings.codeEditor.autoExecution}
                      onChange={(checked) => handleSettingChange('codeEditor.autoExecution', checked)}
                      label="Auto-execute Generated Code"
                      description="Automatically run code when AI generates new visualization commands"
                    />
                  </div>

                  {localSettings.codeEditor.enabled && (
                    <div className="border-t border-gray-200 dark:border-slate-700 pt-4">
                      <div className="font-medium text-gray-900 dark:text-gray-100 text-sm mb-2">Default Startup Code</div>
                      <div className="text-gray-600 dark:text-gray-400 text-xs mb-3">Code template shown when the editor first loads</div>
                      <textarea
                        value={localSettings.codeEditor.defaultCode}
                        onChange={(e) => handleSettingChange('codeEditor.defaultCode', e.target.value)}
                        className="w-full h-32 px-3 py-2 border border-blue-200 dark:border-blue-800 bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-300 dark:focus:border-blue-700 resize-none"
                        placeholder="// Enter default code template..."
                      />
                    </div>
                  )}
                </div>
              )}

              {activeTab === 'interface' && (
                <div className="space-y-1">
                  <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-4">Interface Settings</h3>

                  {/* Theme Selector - Immediate toggle */}
                  <div className="py-3">
                    <div className="font-medium text-gray-900 dark:text-gray-100 text-sm mb-1">Theme</div>
                    <div className="text-gray-600 dark:text-gray-400 text-xs mb-3">Choose your preferred color scheme</div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => {
                          setTheme('light');
                          handleSettingChange('ui.theme', 'light');
                        }}
                        className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-lg border-2 transition-all ${
                          theme === 'light'
                            ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300'
                            : 'border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600 text-gray-900 dark:text-gray-300'
                        }`}
                      >
                        <Sun className="w-5 h-5" />
                        <span className="font-medium">Light</span>
                      </button>
                      <button
                        onClick={() => {
                          setTheme('dark');
                          handleSettingChange('ui.theme', 'dark');
                        }}
                        className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-lg border-2 transition-all ${
                          theme === 'dark'
                            ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300'
                            : 'border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600 text-gray-900 dark:text-gray-300'
                        }`}
                      >
                        <Moon className="w-5 h-5" />
                        <span className="font-medium">Dark</span>
                      </button>
                    </div>
                  </div>

                  <div className="border-t border-gray-200 dark:border-slate-700 pt-1">
                    <Switch
                      checked={localSettings.ui.showQuickPrompts}
                      onChange={(checked) => handleSettingChange('ui.showQuickPrompts', checked)}
                      label="Show Quick Start Prompts"
                      description="Display quick start buttons in the chat panel"
                    />
                  </div>

                  <div className="border-t border-gray-200 dark:border-slate-700 pt-1">
                    <Select
                      value={localSettings.ui.messageHistoryLimit}
                      onChange={(value) => handleSettingChange('ui.messageHistoryLimit', parseInt(value as string))}
                      options={[
                        { value: 25, label: '25 messages' },
                        { value: 50, label: '50 messages' },
                        { value: 100, label: '100 messages' },
                        { value: 200, label: '200 messages' }
                      ]}
                      label="Message History Limit"
                      description="Maximum number of chat messages to keep in memory"
                    />
                  </div>
                </div>
              )}

              {activeTab === 'api' && (
                <div className="space-y-1">
                  <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-4">API Configuration</h3>

                  <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4 mb-4">
                    <div className="flex items-start">
                      <div className="flex-shrink-0">
                        <Zap className="h-5 w-5 text-blue-500 dark:text-blue-400" aria-hidden="true" />
                      </div>
                      <div className="ml-3">
                        <h3 className="text-sm font-medium text-blue-800 dark:text-blue-300">Bring Your Own Key</h3>
                        <div className="mt-2 text-sm text-blue-700 dark:text-blue-400">
                          <p>
                            You can use your own API key to power the AI features.
                            We use <strong>OpenRouter</strong> to access AI models.
                          </p>
                          <p className="mt-1">
                            Your key is stored locally in your browser and sent directly to the server.
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="space-y-4">
                    <div>
                      <label htmlFor="apiKey" className="block text-sm font-medium text-gray-900 dark:text-gray-100">
                        API Key
                      </label>
                      <div className="mt-1">
                        <input
                          type="password"
                          name="apiKey"
                          id="apiKey"
                          className="shadow-sm focus:ring-blue-500 focus:border-blue-500 block w-full sm:text-sm border-gray-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 rounded-md px-3 py-2 border"
                          placeholder="sk-or-..."
                          value={localSettings.api?.key || ''}
                          onChange={(e) => handleSettingChange('api.key', e.target.value)}
                        />
                      </div>
                      <p className="mt-2 text-xs text-gray-600 dark:text-gray-400">
                        Enter your OpenRouter API key (starts with sk-or-).
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === 'chat-history' && (
                <div className="space-y-1">
                  <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-4">Chat History Settings</h3>

                  {/* Storage Statistics */}
                  <div className="bg-gray-50 dark:bg-slate-800/50 border border-gray-200 dark:border-slate-700 rounded-lg p-4 mb-4">
                    <h4 className="font-medium text-gray-900 dark:text-gray-100 text-sm mb-2">Storage Statistics</h4>
                    <div className="space-y-1 text-xs text-gray-700 dark:text-gray-300">
                      {(() => {
                        const stats = getStorageStats();
                        return (
                          <>
                            <div>Total Sessions: {stats.totalSessions}</div>
                            <div>Total Messages: {stats.totalMessages}</div>
                            <div>Storage Used: {stats.estimatedSize}</div>
                          </>
                        );
                      })()}
                    </div>
                  </div>

                  {/* Message History Limit */}
                  <Select
                    value={localSettings.ui.messageHistoryLimit}
                    onChange={(value) => handleSettingChange('ui.messageHistoryLimit', parseInt(value as string))}
                    options={[
                      { value: 25, label: '25 messages' },
                      { value: 50, label: '50 messages' },
                      { value: 100, label: '100 messages' },
                      { value: 200, label: '200 messages' },
                      { value: 500, label: '500 messages' }
                    ]}
                    label="Message History Limit"
                    description="Maximum number of messages to keep per session (affects memory usage)"
                  />

                  {/* Data Management Actions */}
                  <div className="border-t border-gray-200 dark:border-slate-700 pt-4">
                    <h4 className="font-medium text-gray-900 dark:text-gray-100 text-sm mb-3">Data Management</h4>

                    <div className="space-y-3">
                      <div className="flex items-center justify-between p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
                        <div>
                          <div className="font-medium text-blue-900 dark:text-blue-300 text-sm">Export All Sessions</div>
                          <div className="text-blue-700 dark:text-blue-400 text-xs">Download all chat history as JSON backup</div>
                        </div>
                        <button
                          onClick={() => {
                            const data = exportSessions();
                            const blob = new Blob([data], { type: 'application/json' });
                            const url = URL.createObjectURL(blob);
                            const a = document.createElement('a');
                            a.href = url;
                            a.download = `novoprotein-chat-backup-${new Date().toISOString().split('T')[0]}.json`;
                            document.body.appendChild(a);
                            a.click();
                            document.body.removeChild(a);
                            URL.revokeObjectURL(url);
                          }}
                          className="px-3 py-1 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 transition-colors"
                        >
                          Export
                        </button>
                      </div>

                      <div className="flex items-center justify-between p-3 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg">
                        <div>
                          <div className="font-medium text-yellow-900 dark:text-yellow-300 text-sm">Cleanup Old Sessions</div>
                          <div className="text-yellow-700 dark:text-yellow-400 text-xs">Remove sessions older than 30 days (starred sessions are kept)</div>
                        </div>
                        <button
                          onClick={() => {
                            const deleted = cleanupOldSessions(30);
                            alert(`Cleaned up ${deleted} old session(s)`);
                          }}
                          className="px-3 py-1 bg-yellow-600 text-white rounded text-sm hover:bg-yellow-700 transition-colors"
                        >
                          Cleanup
                        </button>
                      </div>

                      <div className="flex items-center justify-between p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
                        <div>
                          <div className="font-medium text-red-900 dark:text-red-300 text-sm">Clear All Chat History</div>
                          <div className="text-red-700 dark:text-red-400 text-xs">Permanently delete all chat sessions and messages</div>
                        </div>
                        <button
                          onClick={() => {
                            if (confirm('Delete ALL chat history? This cannot be undone.')) {
                              clearAllSessions();
                              alert('All chat history has been cleared');
                            }
                          }}
                          className="px-3 py-1 bg-red-600 text-white rounded text-sm hover:bg-red-700 transition-colors"
                        >
                          Clear All
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Auto-cleanup Settings */}
                  <div className="border-t border-gray-200 dark:border-slate-700 pt-4">
                    <h4 className="font-medium text-gray-900 dark:text-gray-100 text-sm mb-3">Auto-cleanup (Future Feature)</h4>
                    <div className="text-xs text-gray-600 dark:text-gray-400 italic">
                      Automatic cleanup of old sessions will be available in a future update.
                      You can manually cleanup old sessions using the button above.
                    </div>
                  </div>
                </div>
              )}

              {activeTab === 'advanced' && (
                <div className="space-y-1">
                  <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-4">Advanced Settings</h3>

                  {/* LangSmith Tracing */}
                  <div className="bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-lg p-4 mb-4">
                    <Switch
                      checked={localSettings.langsmith?.enabled ?? false}
                      onChange={(checked) => handleSettingChange('langsmith.enabled', checked)}
                      label="LangSmith Tracing"
                      description="Send agent traces to LangSmith for debugging and observability. View at smith.langchain.com"
                    />
                    {localSettings.langsmith?.enabled && (
                      <div className="mt-4 pt-4 border-t border-slate-200 dark:border-slate-700 space-y-3">
                        <div>
                          <label htmlFor="langsmithApiKey" className="block text-sm font-medium text-gray-900 dark:text-gray-100">
                            API Key <span className="text-gray-500 font-normal">(optional)</span>
                          </label>
                          <input
                            type="password"
                            id="langsmithApiKey"
                            className="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-slate-600 bg-white dark:bg-slate-700 rounded-md text-sm text-gray-900 dark:text-gray-100 focus:ring-blue-500 focus:border-blue-500"
                            placeholder="lsv2_pt_..."
                            value={localSettings.langsmith?.apiKey || ''}
                            onChange={(e) => handleSettingChange('langsmith.apiKey', e.target.value)}
                          />
                          <p className="mt-1 text-xs text-gray-600 dark:text-gray-400">
                            Use your own LangSmith key, or leave empty to use server env vars.
                          </p>
                        </div>
                        <div>
                          <label htmlFor="langsmithProject" className="block text-sm font-medium text-gray-900 dark:text-gray-100">
                            Project Name
                          </label>
                          <input
                            type="text"
                            id="langsmithProject"
                            className="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-slate-600 bg-white dark:bg-slate-700 rounded-md text-sm text-gray-900 dark:text-gray-100 focus:ring-blue-500 focus:border-blue-500"
                            placeholder="novoprotein-agent"
                            value={localSettings.langsmith?.project || 'novoprotein-agent'}
                            onChange={(e) => handleSettingChange('langsmith.project', e.target.value)}
                          />
                        </div>
                        <a
                          href="https://smith.langchain.com"
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-sm text-blue-600 dark:text-blue-400 hover:underline"
                        >
                          Open smith.langchain.com
                          <ExternalLink className="w-3.5 h-3.5" />
                        </a>
                      </div>
                    )}
                  </div>

                  <Switch
                    checked={localSettings.performance.debugMode}
                    onChange={(checked) => handleSettingChange('performance.debugMode', checked)}
                    label="Debug Mode"
                    description="Enable detailed logging in browser console for troubleshooting"
                  />

                  <div className="border-t border-gray-200 pt-1">
                    <Switch
                      checked={localSettings.performance.enableAnalytics}
                      onChange={(checked) => handleSettingChange('performance.enableAnalytics', checked)}
                      label="Usage Analytics"
                      description="Help improve the app by sharing anonymous usage data (future feature)"
                    />
                  </div>

                  <div className="border-t border-gray-200 dark:border-slate-700 pt-4">
                    <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-4">
                      <h4 className="font-medium text-yellow-800 dark:text-yellow-300 text-sm">Reset Settings</h4>
                      <p className="text-yellow-700 dark:text-yellow-400 text-xs mt-1 mb-3">
                        This will restore all settings to their default values. This cannot be undone.
                      </p>
                      <button
                        onClick={handleReset}
                        className="flex items-center space-x-2 px-3 py-1 bg-yellow-100 text-yellow-800 border border-yellow-300 rounded text-sm hover:bg-yellow-200 transition-colors"
                      >
                        <RotateCcw className="w-4 h-4" />
                        <span>Reset to Defaults</span>
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

      </div>
    </div>
  );
};