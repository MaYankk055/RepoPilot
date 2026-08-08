import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'RepoPilot | Agentic RAG',
  description: 'AI Support Assistant for GitHub Repositories',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
