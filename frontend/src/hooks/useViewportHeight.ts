import { useEffect } from 'react';

/** Keep the in-flow composer above a mobile software keyboard where supported. */
export function useViewportHeight() {
  useEffect(() => {
    const viewport = window.visualViewport;
    const update = () => {
      if (!viewport || viewport.scale === 1) {
        document.documentElement.style.setProperty('--app-height', `${viewport?.height ?? innerHeight}px`);
      }
    };
    update();
    viewport?.addEventListener('resize', update);
    window.addEventListener('resize', update);
    return () => { viewport?.removeEventListener('resize', update); window.removeEventListener('resize', update); };
  }, []);
}
