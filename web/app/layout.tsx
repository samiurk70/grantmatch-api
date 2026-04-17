import type { Metadata, Viewport } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { Navbar } from '@/components/layout/Navbar'
import { Footer } from '@/components/layout/Footer'

const inter = Inter({ subsets: ['latin'], variable: '--font-inter' })

export const metadata: Metadata = {
  metadataBase: new URL('https://grantmatch.io'),
  title: 'GrantMatch — Find UK & EU Grants with ML',
  description:
    'ML-powered grant matching for UK and EU funding. Score 24,699 opportunities from UKRI, Innovate UK, GOV.UK, and Horizon Europe against your project in seconds.',
  openGraph: {
    title: 'GrantMatch — Find UK & EU Grants with ML',
    description: 'Find the right grant in seconds, not days.',
    url: 'https://grantmatch.io',
    siteName: 'GrantMatch',
    images: [{ url: '/og-image.png', width: 1200, height: 630 }],
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'GrantMatch — Find UK & EU Grants with ML',
    description: 'Find the right grant in seconds, not days.',
    images: ['/og-image.png'],
  },
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="flex min-h-screen flex-col antialiased">
        <Navbar />
        <main className="flex flex-1 flex-col pt-20">{children}</main>
        <Footer />
      </body>
    </html>
  )
}
