'use client';

import { useRouter, usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import { supabase } from '@/lib/supabase';
import { useLanguage } from '@/lib/i18n';
import LanguageToggle from '@/components/LanguageToggle';

/**
 * Global navigation component displayed across all pages.
 * Adapts based on authentication state and current route.
 */
export default function GlobalNav() {
  const router = useRouter();
  const pathname = usePathname();
  const { t } = useLanguage();
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);

  useEffect(() => {
    const checkAuth = async () => {
      const { data: { session } } = await supabase.auth.getSession();
      setIsAuthenticated(!!session);
    };
    checkAuth();

    // Listen for auth state changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      setIsAuthenticated(!!session);
    });

    return () => subscription.unsubscribe();
  }, []);

  const handleSignOut = async () => {
    await supabase.auth.signOut();
    router.push('/');
  };

  // Don't show nav on onboarding page
  if (pathname === '/onboarding') {
    return null;
  }

  const isLoginPage = pathname === '/login';
  const isLandingPage = pathname === '/';
  const isDashboard = pathname === '/dashboard';
  const isUpload = pathname === '/upload';
  const isSearch = pathname === '/search';
  const isVideoDetails = pathname?.startsWith('/videos/');

  return (
    <nav className="fixed top-0 w-full bg-white/80 backdrop-blur-md border-b border-gray-200 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          {/* Logo */}
          <div className="flex items-center">
            <button
              onClick={() => router.push(isAuthenticated ? '/dashboard' : '/')}
              className="text-2xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent hover:opacity-80 transition"
            >
              Heimdex
            </button>
          </div>

          {/* Navigation Links - Only show when authenticated */}
          {isAuthenticated && (
            <div className="hidden sm:flex items-center gap-1">
              <button
                onClick={() => router.push('/dashboard')}
                className={`px-4 py-2 rounded-lg transition ${
                  isDashboard
                    ? 'bg-gray-100 text-gray-900 font-medium'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                }`}
              >
                {t.nav.dashboard}
              </button>
              <button
                onClick={() => router.push('/upload')}
                className={`px-4 py-2 rounded-lg transition ${
                  isUpload
                    ? 'bg-gray-100 text-gray-900 font-medium'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                }`}
              >
                {t.nav.upload}
              </button>
              <button
                onClick={() => router.push('/search')}
                className={`px-4 py-2 rounded-lg transition ${
                  isSearch
                    ? 'bg-gray-100 text-gray-900 font-medium'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                }`}
              >
                {t.nav.search}
              </button>
            </div>
          )}

          {/* Right side - Auth actions */}
          <div className="flex items-center gap-4">
            <LanguageToggle />

            {isAuthenticated === null ? (
              // Loading state - don't show on login page
              !isLoginPage && <div className="w-20 h-8 bg-gray-100 rounded animate-pulse" />
            ) : isAuthenticated ? (
              // Authenticated state
              <button
                onClick={handleSignOut}
                className="text-gray-700 hover:text-gray-900 px-4 py-2 rounded-lg hover:bg-gray-100 transition"
              >
                {t.common.signOut}
              </button>
            ) : (
              // Unauthenticated state - don't show auth buttons on login page
              !isLoginPage && (
                <>
                  <button
                    onClick={() => router.push('/login')}
                    className="text-gray-700 hover:text-gray-900 px-4 py-2 rounded-lg hover:bg-gray-100 transition"
                  >
                    {t.common.signIn}
                  </button>
                  <button
                    onClick={() => window.location.href = 'https://calendly.com/j-lee-heimdex/heimdex-demo'}
                    className="bg-gradient-to-r from-blue-600 to-purple-600 text-white px-6 py-2 rounded-lg hover:shadow-lg transition transform hover:scale-105"
                  >
                    {t.landing.getDemo}
                  </button>
                </>
              )
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}
