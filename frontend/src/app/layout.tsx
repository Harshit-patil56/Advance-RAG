import type {Metadata} from 'next';
import {ThemeProvider} from '@/components/ThemeProvider';
import './globals.css';

export const metadata: Metadata = {
  title: 'RAG Intelligence System',
  description: 'Adaptive Domain-Aware RAG-Based Intelligence System for Finance and Law analysis',
};

export default function RootLayout({children}: {children: React.ReactNode}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body suppressHydrationWarning>
        <ThemeProvider>
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
