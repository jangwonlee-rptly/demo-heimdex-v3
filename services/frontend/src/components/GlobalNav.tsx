'use client';

import { useRouter, usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import { supabase } from '@/lib/supabase';
import { useLanguage } from '@/lib/i18n';
import LanguageToggle from '@/components/LanguageToggle';

export default function GlobalNav() {
  const router = useRouter();
  const pathname = usePathname();
  const { t } = useLanguage();
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const checkAuth = async () => {
      const { data: { session } } = await supabase.auth.getSession();
      setIsAuthenticated(!!session);
    };
    checkAuth();

    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      setIsAuthenticated(!!session);
    });

    return () => subscription.unsubscribe();
  }, []);

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 20);
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const handleSignOut = async () => {
    await supabase.auth.signOut();
    router.push('/');
  };

  if (pathname === '/onboarding') {
    return null;
  }

  const isLoginPage = pathname === '/login';
  const isDashboard = pathname === '/dashboard';
  const isUpload = pathname === '/upload';
  const isSearch = pathname === '/search';

  return (
    <nav
      className={`fixed top-0 w-full z-50 transition-all duration-300 ${
        scrolled
          ? 'bg-surface-900/80 backdrop-blur-xl border-b border-surface-700/50'
          : 'bg-transparent'
      }`}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          {/* Logo */}
          <div className="flex items-center gap-8">
            <button
              onClick={() => router.push(isAuthenticated ? '/dashboard' : '/')}
              className="group flex items-center gap-2"
            >
              {/* Logo Icon */}
              <div className="relative w-8 h-8">
                <div className="absolute inset-0 rounded-lg bg-gradient-to-br from-accent-cyan via-accent-violet to-accent-pink opacity-80" />
                <div className="absolute inset-[2px] rounded-[6px] bg-surface-900 flex items-center justify-center">
                  <svg
                    className="w-4 h-4 text-accent-cyan"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <polygon points="23 7 16 12 23 17 23 7" />
                    <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
                  </svg>
                </div>
              </div>
              {/* Logo Text */}
              <span className="text-xl font-bold gradient-text group-hover:opacity-80 transition-opacity">
                Heimdex
              </span>
            </button>

            {/* Navigation Links */}
            {isAuthenticated && (
              <div className="hidden sm:flex items-center gap-1">
                <button
                  onClick={() => router.push('/dashboard')}
                  className={`nav-link ${isDashboard ? 'active' : ''}`}
                >
                  <svg className="w-4 h-4 mr-1.5 inline-block" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <rect x="3" y="3" width="7" height="7" rx="1" />
                    <rect x="14" y="3" width="7" height="7" rx="1" />
                    <rect x="14" y="14" width="7" height="7" rx="1" />
                    <rect x="3" y="14" width="7" height="7" rx="1" />
                  </svg>
                  {t.nav.dashboard}
                </button>
                <button
                  onClick={() => router.push('/upload')}
                  className={`nav-link ${isUpload ? 'active' : ''}`}
                >
                  <svg className="w-4 h-4 mr-1.5 inline-block" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="17 8 12 3 7 8" />
                    <line x1="12" y1="3" x2="12" y2="15" />
                  </svg>
                  {t.nav.upload}
                </button>
                <button
                  onClick={() => router.push('/search')}
                  className={`nav-link ${isSearch ? 'active' : ''}`}
                >
                  <svg className="w-4 h-4 mr-1.5 inline-block" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="11" cy="11" r="8" />
                    <line x1="21" y1="21" x2="16.65" y2="16.65" />
                  </svg>
                  {t.nav.search}
                </button>
              </div>
            )}
          </div>

          {/* Right side */}
          <div className="flex items-center gap-3">
            <LanguageToggle />

            {isAuthenticated === null ? (
              !isLoginPage && (
                <div className="w-20 h-9 rounded-xl bg-surface-700/50 animate-pulse" />
              )
            ) : isAuthenticated ? (
              <button
                onClick={handleSignOut}
                className="btn btn-ghost text-sm"
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                  <polyline points="16 17 21 12 16 7" />
                  <line x1="21" y1="12" x2="9" y2="12" />
                </svg>
                {t.common.signOut}
              </button>
            ) : (
              !isLoginPage && (
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => router.push('/login')}
                    className="btn btn-ghost text-sm"
                  >
                    {t.common.signIn}
                  </button>
                  <button
                    onClick={() => window.location.href = 'https://cal.com/jlee-heimdex/heimdex-demo'}
                    className="btn btn-gradient text-sm"
                  >
                    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <polygon points="5 3 19 12 5 21 5 3" />
                    </svg>
                    {t.landing.getDemo}
                  </button>
                </div>
              )
            )}
          </div>
        </div>
      </div>

      {/* Gradient line at bottom when scrolled */}
      {scrolled && (
        <div className="absolute bottom-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-accent-cyan/20 to-transparent" />
      )}
    </nav>
  );
}
