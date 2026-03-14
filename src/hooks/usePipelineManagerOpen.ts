import { useEffect, useState } from 'react';

/**
 * Manages the pipeline-manager modal state and listens for
 * the custom `open-pipeline-manager` window event dispatched
 * from the chat panel.
 */
export function usePipelineManagerOpen() {
  const [isPipelineManagerOpen, setIsPipelineManagerOpen] = useState(false);

  useEffect(() => {
    const handleOpenPipelineManager = () => {
      setIsPipelineManagerOpen(true);
    };
    window.addEventListener('open-pipeline-manager', handleOpenPipelineManager);
    return () => window.removeEventListener('open-pipeline-manager', handleOpenPipelineManager);
  }, []);

  return { isPipelineManagerOpen, setIsPipelineManagerOpen } as const;
}
