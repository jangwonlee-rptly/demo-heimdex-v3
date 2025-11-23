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
    <div className="flex items-center gap-2">
      <button
        onClick={() => setLanguage(language === 'en' ? 'ko' : 'en')}
        className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg border border-gray-300 bg-white hover:bg-gray-50 transition-colors"
        aria-label="Toggle language"
      >
        <span className="text-lg">{language === 'en' ? '🇺🇸' : '🇰🇷'}</span>
        <span>{language === 'en' ? 'EN' : 'KO'}</span>
      </button>
    </div>
  );
}
