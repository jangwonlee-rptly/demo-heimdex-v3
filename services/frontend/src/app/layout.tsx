import type { Metadata } from 'next';
import './globals.css';
import { LanguageProvider } from '@/lib/i18n';
import GlobalNav from '@/components/GlobalNav';

export const metadata: Metadata = {
  title: 'Heimdex - Vector-Native Video Archive',
  description: 'Search your videos with natural language using AI-powered semantic understanding',
  keywords: ['video', 'archive', 'search', 'AI', 'semantic', 'vector'],
  openGraph: {
    title: 'Heimdex - Vector-Native Video Archive',
    description: 'Search your videos with natural language using AI-powered semantic understanding',
    type: 'website',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body className="font-body antialiased bg-surface-950 text-surface-100">
        <LanguageProvider>
          <GlobalNav />
          <main>
            {children}
          </main>
        </LanguageProvider>
      </body>
    </html>
  );
}
