'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { supabase, apiRequest } from '@/lib/supabase';
import { useLanguage } from '@/lib/i18n';
import LanguageToggle from '@/components/LanguageToggle';

export const dynamic = 'force-dynamic';

/**
 * User onboarding page.
 *
 * Collects profile information from new users such as full name, industry, and job title.
 * Creates a user profile in the backend.
 *
 * @returns {JSX.Element} The onboarding page.
 */
export default function OnboardingPage() {
  const [fullName, setFullName] = useState('');
  const [industry, setIndustry] = useState('');
  const [jobTitle, setJobTitle] = useState('');
  const [preferredLanguage, setPreferredLanguage] = useState('ko'); // Default to Korean
  const [marketingConsent, setMarketingConsent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();
  const { t } = useLanguage();

  useEffect(() => {
    // Check if user is authenticated
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

      // Redirect to dashboard
      router.push('/dashboard');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="absolute top-4 right-4">
        <LanguageToggle />
      </div>
      <div className="card max-w-2xl w-full">
        <h1 className="text-3xl font-bold mb-2">{t.onboarding.title}</h1>
        <p className="text-gray-600 mb-8">
          {t.onboarding.subtitle}
        </p>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label htmlFor="fullName" className="block text-sm font-medium text-gray-700 mb-1">
              {t.onboarding.fullName} <span className="text-red-500">{t.onboarding.fullNameRequired}</span>
            </label>
            <input
              id="fullName"
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="input w-full"
              required
            />
          </div>

          <div>
            <label htmlFor="industry" className="block text-sm font-medium text-gray-700 mb-1">
              {t.onboarding.industry}
            </label>
            <input
              id="industry"
              type="text"
              value={industry}
              onChange={(e) => setIndustry(e.target.value)}
              className="input w-full"
              placeholder={t.onboarding.industryPlaceholder}
            />
          </div>

          <div>
            <label htmlFor="jobTitle" className="block text-sm font-medium text-gray-700 mb-1">
              {t.onboarding.jobTitle}
            </label>
            <input
              id="jobTitle"
              type="text"
              value={jobTitle}
              onChange={(e) => setJobTitle(e.target.value)}
              className="input w-full"
              placeholder={t.onboarding.jobTitlePlaceholder}
            />
          </div>

          <div>
            <label htmlFor="preferredLanguage" className="block text-sm font-medium text-gray-700 mb-1">
              {t.onboarding.preferredLanguage} <span className="text-red-500">{t.onboarding.preferredLanguageRequired}</span>
            </label>
            <p className="text-sm text-gray-500 mb-2">
              {t.onboarding.preferredLanguageHelp}
            </p>
            <select
              id="preferredLanguage"
              value={preferredLanguage}
              onChange={(e) => setPreferredLanguage(e.target.value)}
              className="input w-full"
              required
            >
              <option value="ko">한국어 (Korean)</option>
              <option value="en">English</option>
            </select>
          </div>

          <div className="flex items-start">
            <input
              id="marketingConsent"
              type="checkbox"
              checked={marketingConsent}
              onChange={(e) => setMarketingConsent(e.target.checked)}
              className="mt-1 mr-3"
            />
            <label htmlFor="marketingConsent" className="text-sm text-gray-700">
              {t.onboarding.marketingConsent}
            </label>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
              {error}
            </div>
          )}

          <button
            type="submit"
            className="btn btn-primary w-full"
            disabled={loading || !fullName}
          >
            {loading ? t.onboarding.saving : t.onboarding.completeSetup}
          </button>
        </form>
      </div>
    </div>
  );
}
