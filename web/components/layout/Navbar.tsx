'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Menu, X } from 'lucide-react'

const NAV_LINKS = [
  { href: '/demo', label: 'Demo' },
  { href: '/docs', label: 'API Docs' },
  { href: '/pricing', label: 'Pricing' },
]

export function Navbar() {
  const path = usePathname()
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <>
      <nav className="fixed left-0 right-0 top-0 z-50 px-4 pt-4">
        <div className="glass-flat mx-auto flex max-w-5xl items-center justify-between px-6 py-3">
          {/* Logo */}
          <Link
            href="/"
            className="text-sm font-bold tracking-tight text-white"
            onClick={() => setMenuOpen(false)}
          >
            Grant<span className="text-blue-400">Match</span>
          </Link>

          {/* Desktop nav */}
          <div className="hidden items-center gap-1 md:flex">
            {NAV_LINKS.map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                className={`rounded-lg px-4 py-1.5 text-sm transition-colors
                  ${path === href
                    ? 'bg-white/10 text-white'
                    : 'text-white/55 hover:text-white/80'
                  }`}
              >
                {label}
              </Link>
            ))}
            <Link
              href="/demo"
              className="ml-2 rounded-xl bg-blue-600 px-4 py-1.5 text-sm
                font-medium text-white transition-colors hover:bg-blue-500"
            >
              Try free
            </Link>
          </div>

          {/* Mobile: Try free + hamburger */}
          <div className="flex items-center gap-2 md:hidden">
            <Link
              href="/demo"
              onClick={() => setMenuOpen(false)}
              className="rounded-xl bg-blue-600 px-4 py-1.5 text-sm
                font-medium text-white transition-colors hover:bg-blue-500"
            >
              Try free
            </Link>
            <button
              onClick={() => setMenuOpen(v => !v)}
              className="flex h-11 w-11 items-center justify-center rounded-xl
                text-white/70 transition-colors hover:bg-white/10 hover:text-white"
              aria-label="Toggle menu"
            >
              {menuOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
          </div>
        </div>
      </nav>

      {/* Mobile full-screen overlay menu */}
      <AnimatePresence>
        {menuOpen && (
          <motion.div
            key="mobile-menu"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="glass-flat fixed inset-0 z-40 flex flex-col md:hidden"
            style={{ paddingTop: '5rem' }}
          >
            {/* Close button */}
            <button
              onClick={() => setMenuOpen(false)}
              className="absolute right-6 top-6 flex h-11 w-11 items-center
                justify-center rounded-xl text-white/70 transition-colors
                hover:bg-white/10 hover:text-white"
              aria-label="Close menu"
            >
              <X size={24} />
            </button>

            {/* Nav links */}
            <nav className="flex flex-col px-8 py-8">
              {NAV_LINKS.map(({ href, label }, i) => (
                <motion.div
                  key={href}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.07 + 0.1 }}
                >
                  <Link
                    href={href}
                    onClick={() => setMenuOpen(false)}
                    className={`block border-b border-white/[0.06] py-5 text-xl
                      font-medium transition-colors
                      ${path === href ? 'text-white' : 'text-white/60 hover:text-white'}`}
                  >
                    {label}
                  </Link>
                </motion.div>
              ))}
              <motion.div
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: NAV_LINKS.length * 0.07 + 0.1 }}
                className="pt-6"
              >
                <Link
                  href="/demo"
                  onClick={() => setMenuOpen(false)}
                  className="block rounded-2xl bg-blue-600 py-4 text-center
                    text-lg font-semibold text-white hover:bg-blue-500
                    transition-colors"
                >
                  Try GrantMatch free
                </Link>
              </motion.div>
            </nav>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
