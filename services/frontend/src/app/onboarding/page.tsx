'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { supabase, apiRequest } from '@/lib/supabase';
import { useLanguage } from '@/lib/i18n';
import LanguageToggle from '@/components/LanguageToggle';

export const dynamic = 'force-dynamic';

export default function OnboardingPage() {
  const [fullName, setFullName] = useState('');
  const [industry, setIndustry] = useState('');
  const [jobTitle, setJobTitle] = useState('');
  const [preferredLanguage, setPreferredLanguage] = useState('ko');
  const [marketingConsent, setMarketingConsent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();
  const { t } = useLanguage();

  useEffect(() => {
    const checkAuth = async () => {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) {
        router.push('/login');
      }
    };
    checkAuth();
  }, [router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      await apiRequest('/me/profile', {
        method: 'POST',
        body: JSON.stringify({
          full_name: fullName,
          industry: industry || null,
          job_title: jobTitle || null,
          preferred_language: preferredLanguage,
          marketing_consent: marketingConsent,
        }),
      });

      router.push('/dashboard');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-surface-950">
      {/* Background Effects */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-1/3 left-1/4 w-[500px] h-[500px] bg-accent-violet/8 rounded-full blur-[120px]" />
        <div className="absolute bottom-1/3 right-1/4 w-[400px] h-[400px] bg-accent-cyan/8 rounded-full blur-[100px]" />
      </div>

      {/* Language Toggle */}
      <div className="fixed top-6 right-6">
        <LanguageToggle />
      </div>

      <div className="relative w-full max-w-xl animate-scale-in">
        <div className="card">
          {/* Logo */}
          <div className="flex items-center gap-2 mb-8">
            <div className="relative w-10 h-10">
              <div className="absolute inset-0 rounded-xl bg-gradient-to-br from-accent-cyan via-accent-violet to-accent-pink opacity-80" />
              <div className="absolute inset-[2px] rounded-[10px] bg-surface-800 flex items-center justify-center">
                <svg className="w-5 h-5 text-accent-cyan" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <polygon points="23 7 16 12 23 17 23 7" />
                  <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
                </svg>
              </div>
            </div>
            <span className="text-2xl font-bold gradient-text">Heimdex</span>
          </div>

          <h1 className="text-2xl font-bold text-surface-100 mb-2">{t.onboarding.title}</h1>
          <p className="text-surface-400 mb-8">
            {t.onboarding.subtitle}
          </p>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label htmlFor="fullName" className="label">
                {t.onboarding.fullName} <span className="text-status-error">{t.onboarding.fullNameRequired}</span>
              </label>
              <input
                id="fullName"
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="input"
                placeholder="John Doe"
                required
              />
            </div>

            <div>
              <label htmlFor="industry" className="label">
                {t.onboarding.industry}
              </label>
              <input
                id="industry"
                type="text"
                value={industry}
                onChange={(e) => setIndustry(e.target.value)}
                className="input"
                placeholder={t.onboarding.industryPlaceholder}
              />
            </div>

            <div>
              <label htmlFor="jobTitle" className="label">
                {t.onboarding.jobTitle}
              </label>
              <input
                id="jobTitle"
                type="text"
                value={jobTitle}
                onChange={(e) => setJobTitle(e.target.value)}
                className="input"
                placeholder={t.onboarding.jobTitlePlaceholder}
              />
            </div>

            <div>
              <label htmlFor="preferredLanguage" className="label">
                {t.onboarding.preferredLanguage} <span className="text-status-error">{t.onboarding.preferredLanguageRequired}</span>
              </label>
              <p className="text-xs text-surface-500 mb-2">
                {t.onboarding.preferredLanguageHelp}
              </p>
              <select
                id="preferredLanguage"
                value={preferredLanguage}
                onChange={(e) => setPreferredLanguage(e.target.value)}
                className="select"
                required
              >
                <option value="ko">한국어 (Korean)</option>
                <option value="en">English</option>
              </select>
            </div>

            <div className="flex items-start gap-3 p-4 rounded-xl bg-surface-800/30 border border-surface-700/30">
              <input
                id="marketingConsent"
                type="checkbox"
                checked={marketingConsent}
                onChange={(e) => setMarketingConsent(e.target.checked)}
                className="mt-1 w-4 h-4 rounded border-surface-600 bg-surface-800 text-accent-cyan focus:ring-accent-cyan/50"
              />
              <label htmlFor="marketingConsent" className="text-sm text-surface-400">
                {t.onboarding.marketingConsent}
              </label>
            </div>

            {error && (
              <div className="p-4 rounded-xl bg-status-error/10 border border-status-error/20">
                <div className="flex items-start gap-3">
                  <svg className="w-5 h-5 text-status-error flex-shrink-0 mt-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10" />
                    <line x1="15" y1="9" x2="9" y2="15" />
                    <line x1="9" y1="9" x2="15" y2="15" />
                  </svg>
                  <p className="text-sm text-status-error">{error}</p>
                </div>
              </div>
            )}

            <button
              type="submit"
              className="btn btn-primary w-full btn-lg"
              disabled={loading || !fullName}
            >
              {loading ? (
                <>
                  <div className="w-5 h-5 spinner" />
                  {t.onboarding.saving}
                </>
              ) : (
                <>
                  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                  {t.onboarding.completeSetup}
                </>
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
