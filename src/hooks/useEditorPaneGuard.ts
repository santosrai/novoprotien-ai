import { useEffect } from 'react';
import { useAppStore } from '../stores/appStore';
import { useSettingsStore } from '../stores/settingsStore';

/**
 * Automatically switches away from the editor pane when the
 * code-editor setting is disabled, preventing users from being
 * stuck on an empty pane.
 */
export function useEditorPaneGuard(): void {
  const { activePane, setActivePane } = useAppStore();
  const { settings } = useSettingsStore();

  useEffect(() => {
    if (!settings.codeEditor.enabled && activePane === 'editor') {
      setActivePane('viewer');
    }
  }, [settings.codeEditor.enabled, activePane, setActivePane]);
}
