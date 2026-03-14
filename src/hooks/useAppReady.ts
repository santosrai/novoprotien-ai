import { useEffect } from 'react';

/**
 * Sets a `data-app-ready` attribute on `document.body` after a
 * short delay.  This is used by E2E / integration tests to detect
 * when the React app has finished its initial render.
 */
export function useAppReady(): void {
  useEffect(() => {
    const timer = setTimeout(() => {
      document.body.setAttribute('data-app-ready', 'true');
    }, 500);
    return () => clearTimeout(timer);
  }, []);
}
