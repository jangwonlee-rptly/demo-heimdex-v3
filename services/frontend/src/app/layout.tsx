import type { Metadata } from 'next';
import './globals.css';
import { LanguageProvider } from '@/lib/i18n';
import GlobalNav from '@/components/GlobalNav';

export const metadata: Metadata = {
  title: 'Heimdex - Vector Native Video Archive',
  description: 'Search your videos with natural language',
};

/**
 * Root layout component for the application.
 *
 * @param {Object} props - Component props.
 * @param {React.ReactNode} props.children - The child components to render.
 * @returns {JSX.Element} The root HTML structure.
 */
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <LanguageProvider>
          <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
            <GlobalNav />
            <div className="pt-16">
              {children}
            </div>
          </div>
        </LanguageProvider>
      </body>
    </html>
  );
}
