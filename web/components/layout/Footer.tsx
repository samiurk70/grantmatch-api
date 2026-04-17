import Link from 'next/link'

export function Footer() {
  return (
    <footer className="mt-8 border-t border-white/[0.08]">
      <div className="mx-auto flex max-w-5xl flex-col items-center justify-between gap-4 px-4 py-8 sm:flex-row">
        <p className="text-center text-xs text-white/30 sm:text-left">
          © 2026 GrantMatch. Built on public data from UKRI, Innovate UK,
          GOV.UK, and European Commission CORDIS.
        </p>
        <div className="flex gap-6 text-xs text-white/40">
          <Link href="/demo" className="transition-colors hover:text-white/70">
            Demo
          </Link>
          <Link href="/docs" className="transition-colors hover:text-white/70">
            API Docs
          </Link>
          <Link
            href="/pricing"
            className="transition-colors hover:text-white/70"
          >
            Pricing
          </Link>
          <a
            href="https://github.com/samiurk70/grantmatch-api"
            target="_blank"
            rel="noopener noreferrer"
            className="transition-colors hover:text-white/70"
          >
            GitHub
          </a>
        </div>
      </div>
    </footer>
  )
}
