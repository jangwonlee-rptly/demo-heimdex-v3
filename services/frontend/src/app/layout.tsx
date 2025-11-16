import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Heimdex - Vector Native Video Archive',
  description: 'Search your videos with natural language',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
          {children}
        </div>
      </body>
    </html>
  );
}
