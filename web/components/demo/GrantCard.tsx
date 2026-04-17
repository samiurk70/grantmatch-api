'use client'
import { motion } from 'framer-motion'
import { ExternalLink, Calendar, Building2, ChevronDown } from 'lucide-react'
import { useState } from 'react'
import { ScoreRing } from '@/components/shared/ScoreRing'
import { GlassPanel } from '@/components/shared/GlassPanel'
import type { GrantMatch } from '@/lib/types'

const VERDICT_STYLES = {
  likely_eligible: {
    bg: 'bg-green-500/15',
    text: 'text-green-400',
    border: 'border-green-500/30',
    label: 'Likely Eligible',
  },
  check_required: {
    bg: 'bg-amber-500/15',
    text: 'text-amber-400',
    border: 'border-amber-500/30',
    label: 'Check Required',
  },
  likely_ineligible: {
    bg: 'bg-red-500/15',
    text: 'text-red-400',
    border: 'border-red-500/30',
    label: 'Likely Ineligible',
  },
}

interface GrantCardProps {
  grant: GrantMatch
  index: number
}

export function GrantCard({ grant, index }: GrantCardProps) {
  const [expanded, setExpanded] = useState(false)
  const verdict = VERDICT_STYLES[grant.eligibility_verdict]

  const daysToDeadline = grant.deadline
    ? Math.ceil(
        (new Date(grant.deadline).getTime() - Date.now()) / 86_400_000
      )
    : null

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.08, duration: 0.4, ease: 'easeOut' }}
    >
      <GlassPanel
        padding="md"
        className="group cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        {/* Header row — stack on very narrow screens */}
        <div className="flex flex-col items-start gap-3 xs:flex-row xs:gap-4">
          <ScoreRing score={grant.score} />

          <div className="min-w-0 flex-1">
            <div className="mb-1 flex items-start justify-between gap-2">
              <h3 className="line-clamp-2 text-sm font-semibold leading-snug text-white/90 transition-colors group-hover:text-white">
                {grant.title}
              </h3>
              <motion.div
                animate={{ rotate: expanded ? 180 : 0 }}
                transition={{ duration: 0.2 }}
                className="mt-0.5 shrink-0"
              >
                <ChevronDown size={16} className="text-white/40" />
              </motion.div>
            </div>

            {/* Badges row */}
            <div className="mb-2 flex flex-wrap gap-1.5">
              <span className="inline-flex items-center gap-1 rounded-full border border-blue-500/30 bg-blue-500/20 px-2 py-0.5 text-xs text-blue-300">
                <Building2 size={10} />
                {grant.funder}
              </span>

              {grant.programme && (
                <span className="rounded-full border border-purple-500/25 bg-purple-500/15 px-2 py-0.5 text-xs text-purple-300">
                  {grant.programme}
                </span>
              )}

              <span
                className={`rounded-full border px-2 py-0.5 text-xs
                  ${verdict.bg} ${verdict.text} ${verdict.border}`}
              >
                {verdict.label}
              </span>

              {grant.funding_range !== 'Unknown' && (
                <span className="rounded-full border border-white/10 bg-white/[0.08] px-2 py-0.5 text-xs text-white/60">
                  {grant.funding_range}
                </span>
              )}

              {daysToDeadline !== null && (
                <span
                  className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs
                    ${
                      daysToDeadline < 30
                        ? 'border-red-500/30 bg-red-500/15 text-red-400'
                        : 'border-white/10 bg-white/[0.08] text-white/50'
                    }`}
                >
                  <Calendar size={10} />
                  {daysToDeadline < 0
                    ? 'Closed'
                    : daysToDeadline === 0
                      ? 'Today'
                      : `${daysToDeadline}d left`}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Expanded content */}
        <motion.div
          initial={false}
          animate={{ height: expanded ? 'auto' : 0, opacity: expanded ? 1 : 0 }}
          transition={{ duration: 0.3, ease: 'easeInOut' }}
          className="overflow-hidden"
        >
          <div className="mt-3 space-y-3 border-t border-white/[0.08] pt-3">
            <p className="text-sm leading-relaxed text-white/65">
              {grant.summary}
            </p>

            {/* Top factors */}
            <div>
              <p className="mb-1.5 text-xs uppercase tracking-wider text-white/40">
                Why this matched
              </p>
              <div className="flex flex-wrap gap-1.5">
                {grant.top_factors.map((f, i) => (
                  <span
                    key={i}
                    className={`rounded-full border px-2 py-0.5 text-xs
                      ${
                        f.direction === 'positive'
                          ? 'border-green-500/20 bg-green-500/10 text-green-400'
                          : 'border-red-500/20 bg-red-500/10 text-red-400'
                      }`}
                  >
                    {f.direction === 'positive' ? '+' : '−'}{' '}
                    {f.factor_name.replace(/_/g, ' ')}
                  </span>
                ))}
              </div>
            </div>

            {grant.url && (
              <a
                href={grant.url}
                target="_blank"
                rel="noopener noreferrer"
                onClick={e => e.stopPropagation()}
                className="inline-flex items-center gap-1.5 text-xs
                  text-blue-400 underline underline-offset-2 transition-colors hover:text-blue-300"
              >
                View opportunity
                <ExternalLink size={12} />
              </a>
            )}
          </div>
        </motion.div>
      </GlassPanel>
    </motion.div>
  )
}
