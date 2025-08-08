import React, { useEffect, useRef, useState } from 'react';
import 'molstar/build/viewer/molstar.css';
import { createPluginUI } from 'molstar/lib/mol-plugin-ui';
import { DefaultPluginUISpec } from 'molstar/lib/mol-plugin-ui/spec';
import { PluginUIContext } from 'molstar/lib/mol-plugin-ui/context';
import { renderReact18 } from 'molstar/lib/mol-plugin-ui/react18';
import { Camera, Download, FullscreenIcon, RotateCw } from 'lucide-react';
import { useAppStore } from '../stores/appStore';

export const MolstarViewer: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [plugin, setPlugin] = useState<PluginUIContext | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isInitialized, setIsInitialized] = useState(false);
  const { setPlugin: setStorePlugin } = useAppStore();

  useEffect(() => {
    const initViewer = async () => {
      if (!containerRef.current || isInitialized) return;

      try {
        setIsLoading(true);
        console.log('[Molstar] initViewer: start');
        console.log('[Molstar] initViewer: containerRef set?', !!containerRef.current);

        const pluginInstance = await createPluginUI({
          target: containerRef.current,
          render: renderReact18,
          spec: DefaultPluginUISpec(),
        });
        console.log('[Molstar] createPluginUI: success');

        setPlugin(pluginInstance);
        setStorePlugin(pluginInstance);
        setIsInitialized(true);
        console.log('[Molstar] initViewer: plugin stored and initialized');

        // Load a default structure for demo
        await loadDefaultStructure(pluginInstance);
        console.log('[Molstar] initViewer: default structure loaded');
        
      } catch (error) {
        console.error('[Molstar] initViewer: failed', error);
      } finally {
        setIsLoading(false);
        console.log('[Molstar] initViewer: end (loading=false)');
      }
    };

    void initViewer();

    return () => {
      console.log('[Molstar] cleanup: start');
      if (plugin) {
        try {
          plugin.dispose();
          console.log('[Molstar] cleanup: plugin disposed');
        } catch (e) {
          console.warn('[Molstar] cleanup: dispose failed', e);
        }
        setStorePlugin(null);
      }
      console.log('[Molstar] cleanup: end');
    };
  }, []);

  const loadDefaultStructure = async (pluginInstance: PluginUIContext) => {
    try {
      console.log('[Molstar] loadDefaultStructure: start');
      console.time('[Molstar] download');
      const data = await pluginInstance.builders.data.download({
        url: 'https://files.rcsb.org/view/1CBS.pdb',
        isBinary: false,
      });
      console.timeEnd('[Molstar] download');

      console.time('[Molstar] parseTrajectory');
      const trajectory = await pluginInstance.builders.structure.parseTrajectory(data, 'pdb');
      console.timeEnd('[Molstar] parseTrajectory');

      console.time('[Molstar] createModel');
      const model = await pluginInstance.builders.structure.createModel(trajectory);
      console.timeEnd('[Molstar] createModel');

      console.time('[Molstar] createStructure');
      const structure = await pluginInstance.builders.structure.createStructure(model);
      console.timeEnd('[Molstar] createStructure');

      console.time('[Molstar] addRepresentation');
      await pluginInstance.builders.structure.representation.addRepresentation(structure, {
        type: 'cartoon',
        color: 'secondary-structure'
      });
      console.timeEnd('[Molstar] addRepresentation');

      console.log('[Molstar] loadDefaultStructure: done');
    } catch (error) {
      console.error('[Molstar] loadDefaultStructure: failed', error);
    }
  };

  const handleScreenshot = async () => {
    if (!plugin) return;
    
    try {
      const canvas = plugin.canvas3d?.webgl.gl.canvas;
      if (canvas && 'toDataURL' in canvas) {
        const imageData = (canvas as HTMLCanvasElement).toDataURL('image/png');
        if (imageData) {
          const link = document.createElement('a');
          link.download = 'molstar-screenshot.png';
          link.href = imageData;
          link.click();
        }
      }
    } catch (error) {
      console.error('[Molstar] screenshot failed', error);
    }
  };

  const handleReset = () => {
    if (!plugin) return;
    try {
      plugin.managers.camera.reset();
      console.log('[Molstar] camera reset');
    } catch (e) {
      console.warn('[Molstar] camera reset failed', e);
    }
  };

  const handleFullscreen = () => {
    if (!containerRef.current) return;
    
    if (document.fullscreenElement) {
      void document.exitFullscreen();
    } else {
      void containerRef.current.requestFullscreen();
    }
  };

  return (
    <div className="h-full relative bg-gray-900 overflow-hidden">
      {isLoading && (
        <div className="absolute inset-0 bg-gray-900 flex items-center justify-center z-10">
          <div className="text-white text-center">
            <div className="w-8 h-8 border-2 border-white border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
            <div>Initializing Molstar Viewer...</div>
          </div>
        </div>
      )}

      <div 
        ref={containerRef} 
        className="absolute inset-0 h-full w-full"
      />

      {isInitialized && (
        <div className="absolute top-4 right-4 flex space-x-2 z-20">
          <button
            onClick={handleScreenshot}
            className="p-2 bg-black bg-opacity-50 text-white rounded hover:bg-opacity-70"
            title="Take screenshot"
          >
            <Camera className="w-4 h-4" />
          </button>
          <button
            onClick={handleReset}
            className="p-2 bg-black bg-opacity-50 text-white rounded hover:bg-opacity-70"
            title="Reset camera"
          >
            <RotateCw className="w-4 h-4" />
          </button>
          <button
            onClick={handleFullscreen}
            className="p-2 bg-black bg-opacity-50 text-white rounded hover:bg-opacity-70"
            title="Toggle fullscreen"
          >
            <FullscreenIcon className="w-4 h-4" />
          </button>
        </div>
      )}

      {!isLoading && !isInitialized && (
        <div className="absolute inset-0 bg-gray-900 flex items-center justify-center">
          <div className="text-white text-center">
            <div className="text-red-400 mb-2">Failed to initialize Molstar viewer</div>
            <div className="text-sm text-gray-400">Please refresh the page to try again</div>
          </div>
        </div>
      )}
    </div>
  );
};