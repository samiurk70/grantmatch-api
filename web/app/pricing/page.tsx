import { AnimatedBackground } from '@/components/shared/AnimatedBackground'
import { GlassPanel } from '@/components/shared/GlassPanel'
import Link from 'next/link'
import { ArrowLeft, Check } from 'lucide-react'

export const metadata = {
  title: 'Pricing — GrantMatch',
  description:
    'Free tier for trying GrantMatch; Pro and Teams for API access and collaboration.',
}

const TIERS = [
  {
    name: 'Free',
    price: '£0',
    period: 'forever',
    blurb: 'Try the product and explore matches.',
    features: [
      '50 searches/month',
      'Web app access',
      'All public data sources',
      'Community support',
    ],
    cta: 'Start free',
    href: '/demo',
    highlight: false,
    order: 'order-2 md:order-1',
  },
  {
    name: 'Pro',
    price: '£49',
    period: '/month',
    blurb: 'For teams that need the API and automation.',
    features: [
      'Unlimited searches',
      'API access via secure proxy pattern',
      'Weekly email alerts',
      'Priority support',
    ],
    cta: 'Contact sales',
    href: 'mailto:sales@grantmatch.io',
    highlight: true,
    order: 'order-1 md:order-2',
  },
  {
    name: 'Teams',
    price: '£149',
    period: '/month',
    blurb: 'Multiple keys, analytics, and integrations.',
    features: [
      'Everything in Pro',
      '5 API keys',
      'Usage analytics',
      'Custom integrations',
    ],
    cta: 'Talk to us',
    href: 'mailto:sales@grantmatch.io',
    highlight: false,
    order: 'order-3 md:order-3',
  },
]

export default function PricingPage() {
  return (
    <div className="flex flex-1 flex-col">
      <AnimatedBackground />

      <div className="mx-auto w-full max-w-5xl flex-1 px-4 py-10 sm:px-6 lg:px-8">
        <Link
          href="/"
          className="mb-8 inline-flex items-center gap-2 text-sm text-white/50 transition-colors hover:text-white"
        >
          <ArrowLeft size={16} />
          Back home
        </Link>

        <div className="mb-12 text-center">
          <h1 className="mb-3 text-3xl font-bold text-white sm:text-4xl">
            Pricing
          </h1>
          <p className="mx-auto max-w-xl text-base text-white/55">
            Start free on the web app. Upgrade when you need API access, alerts,
            and team features.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {TIERS.map(
            ({ name, price, period, blurb, features, cta, href, highlight, order }) => (
              <GlassPanel
                key={name}
                padding="lg"
                className={`flex flex-col ${order} ${
                  highlight ? 'border-blue-500/40 bg-blue-500/[0.08]' : ''
                }`}
                hover={false}
              >
                {highlight && (
                  <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-blue-400">
                    Most popular
                  </div>
                )}
                <div className="mb-1 text-3xl font-bold text-white">{price}</div>
                <div className="mb-4 text-sm text-white/40">{period}</div>
                <h2 className="mb-2 text-xl font-semibold text-white">{name}</h2>
                <p className="mb-6 flex-1 text-sm text-white/55">{blurb}</p>
                <ul className="mb-8 space-y-2">
                  {features.map(f => (
                    <li key={f} className="flex items-start gap-2 text-sm text-white/70">
                      <Check
                        size={16}
                        className="mt-0.5 shrink-0 text-green-400"
                      />
                      {f}
                    </li>
                  ))}
                </ul>
                <Link
                  href={href}
                  className={`mt-auto flex min-h-[44px] items-center justify-center rounded-xl text-center text-sm font-semibold transition-colors ${
                    highlight
                      ? 'bg-blue-600 text-white hover:bg-blue-500'
                      : 'glass text-white/80 hover:text-white'
                  }`}
                >
                  {cta}
                </Link>
              </GlassPanel>
            )
          )}
        </div>

        <p className="mt-10 text-center text-xs text-white/35">
          Prices are indicative for the product roadmap. Enterprise and custom
          data licensing available on request.
        </p>
      </div>
    </div>
  )
}
