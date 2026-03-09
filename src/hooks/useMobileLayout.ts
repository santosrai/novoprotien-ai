import { useEffect, useState, useCallback } from 'react';
import { useAppStore } from '../stores/appStore';
import type { MobileTab } from '../components/MobileSegmentedControl';

/**
 * Manages mobile breakpoint detection, tab sync, and tab-change handler.
 *
 * Combines three concerns that are tightly coupled:
 * 1. Window resize → `isMobile` boolean (breakpoint at 768 px)
 * 2. Auto-switch `mobileActiveTab` when the active pane changes
 * 3. `handleMobileTabChange` callback that keeps pane + viewer in sync
 */
export function useMobileLayout() {
  const { activePane, setActivePane, isViewerVisible } = useAppStore();

  const [isMobile, setIsMobile] = useState(() => window.innerWidth < 768);
  const [mobileActiveTab, setMobileActiveTab] = useState<MobileTab>('chat');

  // Track window width → isMobile
  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  // Auto-switch mobile tab when the active pane changes
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

  // User taps a mobile tab → update pane + ensure viewer is visible
  const handleMobileTabChange = useCallback((tab: MobileTab) => {
    setMobileActiveTab(tab);
    if (tab === 'chat') return; // chat doesn't change activePane
    if (tab === 'viewer') {
      setActivePane('viewer');
      if (!isViewerVisible) {
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

  return { isMobile, mobileActiveTab, handleMobileTabChange } as const;
}
