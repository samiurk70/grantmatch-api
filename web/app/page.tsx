import { AnimatedBackground } from '@/components/shared/AnimatedBackground'
import { GlassPanel } from '@/components/shared/GlassPanel'
import {
  ArrowRight,
  Building2,
  GraduationCap,
  Heart,
  Users,
} from 'lucide-react'
import Link from 'next/link'

export default function LandingPage() {
  return (
    <div className="flex flex-1 flex-col">
      <AnimatedBackground />

      {/* HERO */}
      <section className="mx-auto max-w-5xl px-4 pb-12 pt-8 text-center sm:px-6 lg:px-8 md:pb-20 md:pt-12">
        <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-blue-500/25 bg-blue-500/10 px-4 py-1.5 text-xs text-blue-300">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-green-400" />
          Live · 24,699 grants indexed · Updated weekly
        </div>

        <h1 className="mb-6 bg-gradient-to-br from-white via-white/90 to-white/50 bg-clip-text text-4xl font-bold tracking-tight text-transparent sm:text-5xl md:text-6xl lg:text-7xl">
          Find the right grant
          <br />
          <span className="bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
            in seconds, not days
          </span>
        </h1>

        <p className="mx-auto mb-10 max-w-2xl text-base leading-relaxed text-white/55 sm:text-lg md:text-xl">
          GrantMatch uses ML to score 24,699 UK and EU funding opportunities
          against your project — instantly. No keyword guessing. No hours of
          research.
        </p>

        <div className="flex flex-col items-stretch justify-center gap-3 sm:flex-row sm:items-center sm:justify-center">
          <Link
            href="/demo"
            className="group flex items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-blue-600 to-blue-500 px-8 py-4 text-sm font-semibold text-white shadow-[0_0_40px_rgba(79,142,247,0.4)] transition-all duration-300 hover:from-blue-500 hover:to-blue-400 hover:shadow-[0_0_60px_rgba(79,142,247,0.6)] sm:w-auto"
          >
            Try the demo — it&apos;s free
            <ArrowRight
              size={16}
              className="transition-transform group-hover:translate-x-1"
            />
          </Link>
          <Link
            href="/docs"
            className="glass flex items-center justify-center gap-2 rounded-2xl px-8 py-4 text-sm font-medium text-white/80 transition-colors hover:text-white sm:w-auto"
          >
            API documentation
          </Link>
        </div>
      </section>

      {/* STATS BAR */}
      <section className="mx-auto max-w-4xl px-4 pb-12 sm:px-6 lg:px-8 md:pb-16">
        <GlassPanel hover={false} padding="md">
          <div className="grid grid-cols-2 gap-6 sm:grid-cols-4">
            {[
              { n: '24,699', label: 'Grants indexed' },
              { n: '4', label: 'Data sources' },
              { n: '<500ms', label: 'Search time' },
              { n: 'Free', label: 'To try' },
            ].map(({ n, label }) => (
              <div key={label} className="text-center">
                <div className="mb-1 text-2xl font-bold text-white">{n}</div>
                <div className="text-xs text-white/45">{label}</div>
              </div>
            ))}
          </div>
        </GlassPanel>
      </section>

      {/* HOW IT WORKS */}
      <section className="mx-auto max-w-5xl px-4 pb-12 sm:px-6 lg:px-8 md:pb-20">
        <h2 className="mb-3 text-center text-2xl font-bold text-white sm:text-3xl">
          How it works
        </h2>
        <p className="mb-10 text-center text-sm text-white/50 sm:mb-12 sm:text-base">
          Three steps from description to ranked results
        </p>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {[
            {
              icon: '📝',
              step: '01',
              title: 'Describe your project',
              desc: 'Tell us what you are building, your sector, organisation type, and how much funding you need.',
            },
            {
              icon: '⚡',
              step: '02',
              title: 'ML scoring',
              desc: 'Our model embeds your description and runs semantic search across 24,699 grants, then re-ranks with XGBoost.',
            },
            {
              icon: '🎯',
              step: '03',
              title: 'Ranked results',
              desc: 'Get a prioritised shortlist with match scores, eligibility verdicts, and explanations for each result.',
            },
          ].map(({ icon, step, title, desc }) => (
            <GlassPanel key={step} padding="lg" className="relative">
              <div className="mb-4 text-3xl">{icon}</div>
              <div className="mb-2 font-mono text-xs text-blue-400/60">
                STEP {step}
              </div>
              <h3 className="mb-2 font-semibold text-white">{title}</h3>
              <p className="text-sm leading-relaxed text-white/55">{desc}</p>
            </GlassPanel>
          ))}
        </div>
      </section>

      {/* WHO IT'S FOR */}
      <section className="mx-auto max-w-5xl px-4 pb-12 sm:px-6 lg:px-8 md:pb-20">
        <h2 className="mb-3 text-center text-2xl font-bold text-white sm:text-3xl">
          Who it&apos;s for
        </h2>
        <p className="mb-10 text-center text-sm text-white/50 sm:mb-12 sm:text-base">
          Built for anyone seeking UK or EU funding
        </p>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {[
            {
              Icon: Building2,
              colour: 'text-blue-400',
              bg: 'bg-blue-500/15',
              title: 'Startups & SMEs',
              desc: 'Stop spending hours on grant research. Get a ranked shortlist in under a second and apply with confidence.',
            },
            {
              Icon: GraduationCap,
              colour: 'text-purple-400',
              bg: 'bg-purple-500/15',
              title: 'University researchers',
              desc: 'Surface UKRI, EPSRC, and Horizon Europe funding relevant to your research area automatically.',
            },
            {
              Icon: Users,
              colour: 'text-teal-400',
              bg: 'bg-teal-500/15',
              title: 'Innovation consultants',
              desc: 'Integrate via API. Add ML-powered grant matching to your own tools at £149/month.',
            },
            {
              Icon: Heart,
              colour: 'text-pink-400',
              bg: 'bg-pink-500/15',
              title: 'Charities & social enterprises',
              desc: 'Find GOV.UK grants and social investment opportunities matched to your mission and location.',
            },
          ].map(({ Icon, colour, bg, title, desc }) => (
            <GlassPanel key={title} padding="lg">
              <div className={`mb-4 inline-flex rounded-xl p-3 ${bg}`}>
                <Icon size={20} className={colour} />
              </div>
              <h3 className="mb-2 font-semibold text-white">{title}</h3>
              <p className="text-sm leading-relaxed text-white/55">{desc}</p>
            </GlassPanel>
          ))}
        </div>
      </section>

      {/* PRICING — Pro first on mobile */}
      <section className="mx-auto max-w-4xl px-4 pb-12 sm:px-6 lg:px-8 md:pb-20">
        <h2 className="mb-3 text-center text-2xl font-bold text-white sm:text-3xl">
          Simple pricing
        </h2>
        <p className="mb-10 text-center text-sm text-white/50 sm:mb-12 sm:text-base">
          Start free. Upgrade when you need more.
        </p>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {[
            {
              name: 'Free',
              price: '£0',
              period: 'forever',
              features: [
                '50 searches/month',
                'Web app access',
                'All grant sources',
                'No API access',
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
              features: [
                'Unlimited searches',
                'API access',
                'Weekly email alerts',
                'Priority support',
              ],
              cta: 'Get Pro',
              href: '/pricing',
              highlight: true,
              order: 'order-1 md:order-2',
            },
            {
              name: 'Teams',
              price: '£149',
              period: '/month',
              features: [
                'Everything in Pro',
                '5 API keys',
                'Usage analytics',
                'Custom integrations',
              ],
              cta: 'Get Teams',
              href: '/pricing',
              highlight: false,
              order: 'order-3 md:order-3',
            },
          ].map(({ name, price, period, features, cta, href, highlight, order }) => (
            <GlassPanel
              key={name}
              padding="lg"
              className={`${order} ${highlight ? 'border-blue-500/40 bg-blue-500/[0.08]' : ''}`}
            >
              {highlight && (
                <div className="mb-3 text-xs font-semibold uppercase tracking-wider text-blue-400">
                  Most popular
                </div>
              )}
              <div className="mb-4">
                <span className="text-3xl font-bold text-white">{price}</span>
                <span className="ml-1 text-sm text-white/40">{period}</span>
              </div>
              <div className="mb-4 font-semibold text-white">{name}</div>
              <ul className="mb-6 space-y-2">
                {features.map(f => (
                  <li
                    key={f}
                    className="flex items-center gap-2 text-sm text-white/60"
                  >
                    <span className="text-xs text-green-400">✓</span>
                    {f}
                  </li>
                ))}
              </ul>
              <Link
                href={href}
                className={`block rounded-xl py-2.5 text-center text-sm font-medium transition-all duration-200 ${
                  highlight
                    ? 'bg-blue-600 text-white hover:bg-blue-500'
                    : 'glass text-white/70 hover:text-white'
                }`}
              >
                {cta}
              </Link>
            </GlassPanel>
          ))}
        </div>
      </section>

      {/* DATA SOURCES */}
      <section className="mx-auto max-w-3xl px-4 pb-12 text-center sm:px-6 lg:px-8 md:pb-20">
        <p className="mb-4 text-xs uppercase tracking-widest text-white/30">
          Data from
        </p>
        <div className="flex flex-wrap justify-center gap-6 text-sm text-white/40">
          {[
            'UKRI Gateway to Research',
            'Innovate UK',
            'GOV.UK Find a Grant',
            'European Commission CORDIS',
          ].map(s => (
            <span key={s} className="flex items-center gap-1.5">
              <span className="h-1 w-1 rounded-full bg-white/25" />
              {s}
            </span>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="mx-auto max-w-3xl px-4 pb-20 text-center sm:px-6 lg:px-8 md:pb-28">
        <GlassPanel padding="lg" hover={false}>
          <h2 className="mb-3 text-2xl font-bold text-white sm:text-3xl">
            Ready to find your funding?
          </h2>
          <p className="mb-6 text-white/55">Free to try. No account required.</p>
          <Link
            href="/demo"
            className="group inline-flex items-center gap-2 rounded-2xl bg-gradient-to-r from-blue-600 to-blue-500 px-8 py-4 text-sm font-semibold text-white shadow-[0_0_40px_rgba(79,142,247,0.4)] transition-all duration-300 hover:from-blue-500 hover:to-blue-400 hover:shadow-[0_0_60px_rgba(79,142,247,0.6)]"
          >
            Try GrantMatch free
            <ArrowRight
              size={16}
              className="transition-transform group-hover:translate-x-1"
            />
          </Link>
        </GlassPanel>
      </section>
    </div>
  )
}
