import { useEffect, useState } from 'react';

export type ThemePreference = 'system' | 'light' | 'dark';
export const THEME_KEY = 'hll-theme';

export function readThemePreference(): ThemePreference {
  try {
    const value = localStorage.getItem(THEME_KEY);
    return value === 'light' || value === 'dark' ? value : 'system';
  } catch { return 'system'; }
}

export function useTheme() {
  const [preference, setPreference] = useState<ThemePreference>(readThemePreference);
  useEffect(() => {
    const media = matchMedia('(prefers-color-scheme: dark)');
    const apply = () => {
      const theme = preference === 'system' ? (media.matches ? 'dark' : 'light') : preference;
      document.documentElement.dataset.theme = theme;
      document.documentElement.style.colorScheme = theme;
    };
    apply();
    media.addEventListener('change', apply);
    return () => media.removeEventListener('change', apply);
  }, [preference]);
  const changeTheme = (value: ThemePreference) => {
    setPreference(value);
    try { localStorage.setItem(THEME_KEY, value); } catch { /* Private mode still supports in-memory themes. */ }
  };
  return { preference, changeTheme };
}
