import { AnimatedBackground } from '@/components/shared/AnimatedBackground'
import { GlassPanel } from '@/components/shared/GlassPanel'
import Link from 'next/link'
import { ArrowLeft, BookOpen, Key, Server } from 'lucide-react'

export const metadata = {
  title: 'API Documentation — GrantMatch',
  description:
    'GrantMatch REST API: match profiles to grants, browse the catalogue, and health checks.',
}

export default function DocsPage() {
  return (
    <div className="flex flex-1 flex-col">
      <AnimatedBackground />

      <div className="mx-auto w-full max-w-3xl flex-1 px-4 py-10 sm:px-6 lg:px-8">
        <Link
          href="/"
          className="mb-8 inline-flex items-center gap-2 text-sm text-white/50 transition-colors hover:text-white"
        >
          <ArrowLeft size={16} />
          Back home
        </Link>

        <div className="mb-10">
          <div className="mb-4 inline-flex items-center gap-2 text-blue-400">
            <BookOpen size={20} />
            <span className="text-sm font-medium uppercase tracking-wider">
              Reference
            </span>
          </div>
          <h1 className="mb-3 text-3xl font-bold text-white sm:text-4xl">
            GrantMatch API
          </h1>
          <p className="text-base text-white/55">
            The backend exposes versioned JSON endpoints under{' '}
            <code className="rounded bg-white/10 px-1.5 py-0.5 text-sm text-blue-300">
              /api/v1
            </code>
            . From this web app, call the secure Next.js proxy at{' '}
            <code className="rounded bg-white/10 px-1.5 py-0.5 text-sm text-blue-300">
              POST /api/match
            </code>{' '}
            — never put your API key in browser code.
          </p>
        </div>

        <div className="space-y-6">
          <GlassPanel padding="lg" hover={false}>
            <div className="mb-4 flex items-center gap-2 text-white">
              <Key size={18} className="text-amber-400" />
              <h2 className="text-lg font-semibold">Authentication</h2>
            </div>
            <p className="text-sm leading-relaxed text-white/60">
              Server-to-server calls use the{' '}
              <code className="text-blue-300">X-API-Key</code> header. The
              hosted FastAPI docs live on your Railway deployment at{' '}
              <code className="text-white/80">/docs</code> (Swagger UI).
            </p>
          </GlassPanel>

          <GlassPanel padding="lg" hover={false}>
            <div className="mb-4 flex items-center gap-2 text-white">
              <Server size={18} className="text-teal-400" />
              <h2 className="text-lg font-semibold">Endpoints</h2>
            </div>
            <ul className="space-y-3 text-sm text-white/65">
              <li className="flex flex-col gap-1 border-b border-white/[0.06] pb-3 sm:flex-row sm:items-center sm:justify-between">
                <span className="font-mono text-green-400">GET /api/v1/</span>
                <span className="text-white/45">API info and links</span>
              </li>
              <li className="flex flex-col gap-1 border-b border-white/[0.06] pb-3 sm:flex-row sm:items-center sm:justify-between">
                <span className="font-mono text-green-400">
                  GET /api/v1/health
                </span>
                <span className="text-white/45">Health — DB, index, model</span>
              </li>
              <li className="flex flex-col gap-1 border-b border-white/[0.06] pb-3 sm:flex-row sm:items-center sm:justify-between">
                <span className="font-mono text-blue-400">
                  POST /api/v1/match
                </span>
                <span className="text-white/45">
                  Match an applicant profile (requires API key)
                </span>
              </li>
              <li className="flex flex-col gap-1 border-b border-white/[0.06] pb-3 sm:flex-row sm:items-center sm:justify-between">
                <span className="font-mono text-blue-400">
                  GET /api/v1/grants
                </span>
                <span className="text-white/45">Browse grants (filters)</span>
              </li>
              <li className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                <span className="font-mono text-blue-400">
                  GET /api/v1/grants/&#123;id&#125;
                </span>
                <span className="text-white/45">Single grant by ID</span>
              </li>
            </ul>
          </GlassPanel>

          <GlassPanel padding="lg" hover={false}>
            <h2 className="mb-3 text-lg font-semibold text-white">
              Next.js proxy (browser-safe)
            </h2>
            <p className="mb-4 text-sm leading-relaxed text-white/60">
              The demo calls{' '}
              <code className="text-blue-300">POST /api/match</code> on this
              site. That route forwards the body to your GrantMatch backend with
              the secret key stored in Vercel/Railway env vars — the key never
              ships to the client.
            </p>
            <Link
              href="/demo"
              className="inline-flex min-h-[44px] items-center justify-center rounded-xl bg-blue-600 px-5 text-sm font-medium text-white transition-colors hover:bg-blue-500"
            >
              Open interactive demo
            </Link>
          </GlassPanel>
        </div>
      </div>
    </div>
  )
}
