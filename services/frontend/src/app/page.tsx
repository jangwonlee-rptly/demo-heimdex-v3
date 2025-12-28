'use client';

/**
 * Landing Page.
 *
 * Displays marketing content and entry points for login/signup.
 * Redirects authenticated users to the dashboard.
 */

import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { supabase } from '@/lib/supabase';
import { useLanguage } from '@/lib/i18n';

export const dynamic = 'force-dynamic';

export default function LandingPage() {
  const router = useRouter();
  const [isCheckingAuth, setIsCheckingAuth] = useState(true);
  const { t } = useLanguage();

  useEffect(() => {
    const checkAuth = async () => {
      const { data: { session } } = await supabase.auth.getSession();
      if (session) {
        router.push('/dashboard');
      } else {
        setIsCheckingAuth(false);
      }
    };
    checkAuth();
  }, [router]);

  if (isCheckingAuth) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-surface-950">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 spinner" />
          <p className="text-surface-400">{t.common.loading}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-surface-950 overflow-hidden">
      {/* Background Effects */}
      <div className="fixed inset-0 pointer-events-none">
        {/* Gradient orbs */}
        <div className="absolute top-0 left-1/4 w-[600px] h-[600px] bg-accent-cyan/10 rounded-full blur-[120px] animate-float" />
        <div className="absolute top-1/3 right-1/4 w-[500px] h-[500px] bg-accent-violet/10 rounded-full blur-[100px] animate-float" style={{ animationDelay: '1s' }} />
        <div className="absolute bottom-0 left-1/2 w-[400px] h-[400px] bg-accent-pink/8 rounded-full blur-[80px]" />
        {/* Grid pattern */}
        <div
          className="absolute inset-0 opacity-[0.02]"
          style={{
            backgroundImage: `linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)`,
            backgroundSize: '60px 60px'
          }}
        />
      </div>

      {/* Hero Section */}
      <section className="relative pt-32 pb-24 px-4 sm:px-6 lg:px-8">
        <div className="max-w-5xl mx-auto text-center">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-surface-800/50 border border-surface-700/50 mb-8 animate-fade-in">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent-cyan opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-accent-cyan"></span>
            </span>
            <span className="text-sm text-surface-300">Vector-Native Video Intelligence</span>
          </div>

          {/* Headline */}
          <h1 className="text-5xl sm:text-6xl lg:text-7xl font-bold mb-6 tracking-tight animate-slide-up">
            <span className="text-surface-100">{t.landing.heroTitle1}</span>
            <br />
            <span className="gradient-text">{t.landing.heroTitle2}</span>
          </h1>

          {/* Subtitle */}
          <p className="text-xl sm:text-2xl text-surface-400 mb-12 max-w-3xl mx-auto leading-relaxed animate-slide-up" style={{ animationDelay: '0.1s' }}>
            {t.landing.heroDescription}
          </p>

          {/* CTA Buttons */}
          <div className="flex flex-col sm:flex-row gap-4 justify-center animate-slide-up" style={{ animationDelay: '0.2s' }}>
            <button
              onClick={() => window.location.href = 'https://cal.com/jlee-heimdex/heimdex-demo'}
              className="btn btn-gradient btn-lg group"
            >
              <svg className="w-5 h-5 transition-transform group-hover:scale-110" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polygon points="5 3 19 12 5 21 5 3" />
              </svg>
              {t.landing.requestDemo}
            </button>
            <button
              onClick={() => router.push('/login')}
              className="btn btn-secondary btn-lg"
            >
              {t.landing.getStarted}
              <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="5" y1="12" x2="19" y2="12" />
                <polyline points="12 5 19 12 12 19" />
              </svg>
            </button>
          </div>

          {/* Stats */}
          <div className="mt-20 grid grid-cols-3 gap-8 max-w-2xl mx-auto animate-slide-up" style={{ animationDelay: '0.3s' }}>
            <div className="text-center">
              <div className="text-3xl font-bold gradient-text-subtle mb-1">10x</div>
              <div className="text-sm text-surface-500">Faster Search</div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold gradient-text-subtle mb-1">99%</div>
              <div className="text-sm text-surface-500">Accuracy</div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold gradient-text-subtle mb-1">24/7</div>
              <div className="text-sm text-surface-500">Processing</div>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="relative py-24 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold text-surface-100 mb-4">
              {t.landing.featuresTitle}
            </h2>
            <p className="text-lg text-surface-400 max-w-2xl mx-auto">
              {t.landing.featuresSubtitle}
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            {/* Feature 1 */}
            <div className="feature-card group">
              <div className="feature-card-inner">
                <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-accent-cyan/20 to-accent-cyan/5 flex items-center justify-center mb-5 group-hover:scale-110 transition-transform">
                  <svg className="w-7 h-7 text-accent-cyan" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="11" cy="11" r="8" />
                    <line x1="21" y1="21" x2="16.65" y2="16.65" />
                    <line x1="11" y1="8" x2="11" y2="14" />
                    <line x1="8" y1="11" x2="14" y2="11" />
                  </svg>
                </div>
                <h3 className="text-xl font-semibold text-surface-100 mb-3">
                  {t.landing.feature1Title}
                </h3>
                <p className="text-surface-400 leading-relaxed">
                  {t.landing.feature1Description}
                </p>
              </div>
            </div>

            {/* Feature 2 */}
            <div className="feature-card group">
              <div className="feature-card-inner">
                <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-accent-violet/20 to-accent-violet/5 flex items-center justify-center mb-5 group-hover:scale-110 transition-transform">
                  <svg className="w-7 h-7 text-accent-violet" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
                  </svg>
                </div>
                <h3 className="text-xl font-semibold text-surface-100 mb-3">
                  {t.landing.feature2Title}
                </h3>
                <p className="text-surface-400 leading-relaxed">
                  {t.landing.feature2Description}
                </p>
              </div>
            </div>

            {/* Feature 3 */}
            <div className="feature-card group">
              <div className="feature-card-inner">
                <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-accent-pink/20 to-accent-pink/5 flex items-center justify-center mb-5 group-hover:scale-110 transition-transform">
                  <svg className="w-7 h-7 text-accent-pink" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                    <polyline points="9 12 11 14 15 10" />
                  </svg>
                </div>
                <h3 className="text-xl font-semibold text-surface-100 mb-3">
                  {t.landing.feature3Title}
                </h3>
                <p className="text-surface-400 leading-relaxed">
                  {t.landing.feature3Description}
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section className="relative py-24 px-4 sm:px-6 lg:px-8">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold text-surface-100 mb-4">
              {t.landing.howItWorksTitle}
            </h2>
            <p className="text-lg text-surface-400 max-w-2xl mx-auto">
              {t.landing.howItWorksSubtitle}
            </p>
          </div>

          <div className="relative">
            {/* Connection line */}
            <div className="hidden md:block absolute top-14 left-1/6 right-1/6 h-[2px] bg-gradient-to-r from-accent-cyan via-accent-violet to-accent-pink opacity-30" />

            <div className="grid md:grid-cols-3 gap-12">
              {/* Step 1 */}
              <div className="text-center">
                <div className="relative inline-flex mb-6">
                  <div className="w-28 h-28 rounded-full bg-gradient-to-br from-accent-cyan/20 to-transparent flex items-center justify-center">
                    <div className="w-20 h-20 rounded-full bg-surface-800 border border-surface-700 flex items-center justify-center">
                      <span className="text-3xl font-bold gradient-text">1</span>
                    </div>
                  </div>
                </div>
                <h3 className="text-xl font-semibold text-surface-100 mb-2">
                  {t.landing.step1Title}
                </h3>
                <p className="text-surface-400">
                  {t.landing.step1Description}
                </p>
              </div>

              {/* Step 2 */}
              <div className="text-center">
                <div className="relative inline-flex mb-6">
                  <div className="w-28 h-28 rounded-full bg-gradient-to-br from-accent-violet/20 to-transparent flex items-center justify-center">
                    <div className="w-20 h-20 rounded-full bg-surface-800 border border-surface-700 flex items-center justify-center">
                      <span className="text-3xl font-bold gradient-text">2</span>
                    </div>
                  </div>
                </div>
                <h3 className="text-xl font-semibold text-surface-100 mb-2">
                  {t.landing.step2Title}
                </h3>
                <p className="text-surface-400">
                  {t.landing.step2Description}
                </p>
              </div>

              {/* Step 3 */}
              <div className="text-center">
                <div className="relative inline-flex mb-6">
                  <div className="w-28 h-28 rounded-full bg-gradient-to-br from-accent-pink/20 to-transparent flex items-center justify-center">
                    <div className="w-20 h-20 rounded-full bg-surface-800 border border-surface-700 flex items-center justify-center">
                      <span className="text-3xl font-bold gradient-text">3</span>
                    </div>
                  </div>
                </div>
                <h3 className="text-xl font-semibold text-surface-100 mb-2">
                  {t.landing.step3Title}
                </h3>
                <p className="text-surface-400">
                  {t.landing.step3Description}
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="relative py-24 px-4 sm:px-6 lg:px-8">
        <div className="max-w-4xl mx-auto">
          <div className="relative rounded-3xl overflow-hidden">
            {/* Background gradient */}
            <div className="absolute inset-0 bg-gradient-to-br from-accent-cyan/20 via-accent-violet/20 to-accent-pink/20" />
            <div className="absolute inset-0 bg-surface-900/80 backdrop-blur-xl" />

            {/* Content */}
            <div className="relative px-8 py-16 sm:px-16 text-center">
              <h2 className="text-3xl sm:text-4xl font-bold text-surface-100 mb-4">
                {t.landing.ctaTitle}
              </h2>
              <p className="text-lg text-surface-400 mb-8 max-w-xl mx-auto">
                {t.landing.ctaDescription}
              </p>
              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <button
                  onClick={() => window.location.href = 'https://cal.com/jlee-heimdex/heimdex-demo'}
                  className="btn btn-primary btn-lg"
                >
                  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                    <line x1="16" y1="2" x2="16" y2="6" />
                    <line x1="8" y1="2" x2="8" y2="6" />
                    <line x1="3" y1="10" x2="21" y2="10" />
                  </svg>
                  {t.landing.scheduleDemo}
                </button>
                <button
                  onClick={() => window.location.href = 'https://cal.com/jlee-heimdex/heimdex-demo'}
                  className="btn btn-secondary btn-lg"
                >
                  {t.landing.contactSales}
                </button>
              </div>
            </div>

            {/* Decorative elements */}
            <div className="absolute top-0 right-0 w-64 h-64 bg-accent-cyan/10 rounded-full blur-[80px]" />
            <div className="absolute bottom-0 left-0 w-64 h-64 bg-accent-violet/10 rounded-full blur-[80px]" />
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="relative py-12 px-4 sm:px-6 lg:px-8 border-t border-surface-800">
        <div className="max-w-7xl mx-auto">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <div className="relative w-6 h-6">
                <div className="absolute inset-0 rounded bg-gradient-to-br from-accent-cyan via-accent-violet to-accent-pink opacity-80" />
                <div className="absolute inset-[1px] rounded bg-surface-900 flex items-center justify-center">
                  <svg className="w-3 h-3 text-accent-cyan" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <polygon points="23 7 16 12 23 17 23 7" />
                    <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
                  </svg>
                </div>
              </div>
              <span className="text-lg font-bold gradient-text">Heimdex</span>
            </div>
            <p className="text-surface-500 text-sm">{t.landing.footerTagline}</p>
            <p className="text-surface-600 text-sm">{t.landing.footerCopyright}</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
