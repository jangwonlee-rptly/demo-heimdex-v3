'use client';

import { useLanguage } from '@/lib/i18n';

/**
 * A component to toggle between English and Korean languages.
 *
 * @returns {JSX.Element} The language toggle button.
 */
export default function LanguageToggle() {
  const { language, setLanguage } = useLanguage();

  return (
    <button
      onClick={() => setLanguage(language === 'en' ? 'ko' : 'en')}
      className="px-3 py-1.5 text-sm font-medium rounded-lg bg-surface-800/60 border border-surface-700/50 text-surface-300 hover:text-surface-100 hover:bg-surface-700/60 hover:border-surface-600/50 transition-all"
      aria-label="Toggle language"
    >
      {language === 'en' ? 'EN' : 'KO'}
    </button>
  );
}
