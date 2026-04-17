'use client'
import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { SearchForm } from '@/components/demo/SearchForm'
import { GrantCard } from '@/components/demo/GrantCard'
import { AnimatedBackground } from '@/components/shared/AnimatedBackground'
import { GlassPanel } from '@/components/shared/GlassPanel'
import { matchGrants } from '@/lib/api'
import type { ApplicantProfile, MatchResponse } from '@/lib/types'
import { Zap, Database, Brain } from 'lucide-react'

export default function DemoPage() {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<MatchResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleSearch = async (profile: ApplicantProfile) => {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await matchGrants(profile)
      setResult(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen">
      <AnimatedBackground />

      <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6 lg:px-8">
        {/* Page header */}
        <div className="mb-10 text-center sm:mb-12">
          <h1 className="mb-3 text-3xl font-bold text-white sm:text-4xl">
            Find Your Grants
          </h1>
          <p className="text-base text-white/60 sm:text-lg">
            Describe your project and we&apos;ll score 24,699 grants instantly
          </p>
        </div>

        {/* Two-column layout: form left, results right */}
        <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[420px_1fr]">
          {/* Search form — sticky on desktop only */}
          <div className="lg:sticky lg:top-8">
            <SearchForm onSearch={handleSearch} loading={loading} />
          </div>

          {/* Results panel */}
          <div>
            <AnimatePresence mode="wait">
              {result && (
                <motion.div
                  key="results"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                >
                  {/* Results header */}
                  <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <h2 className="font-semibold text-white">
                        {result.total_matched} grants matched
                      </h2>
                      <p className="mt-0.5 text-xs text-white/40">
                        Scored in {result.processing_time_ms.toFixed(0)}ms ·
                        Data from {result.data_freshness}
                      </p>
                    </div>
                    <div className="hidden gap-2 text-xs text-white/40 sm:flex">
                      <span className="flex items-center gap-1">
                        <Zap size={12} className="text-blue-400" />
                        FAISS search
                      </span>
                      <span className="flex items-center gap-1">
                        <Brain size={12} className="text-purple-400" />
                        ML ranked
                      </span>
                      <span className="flex items-center gap-1">
                        <Database size={12} className="text-teal-400" />
                        {result.grants.length} shown
                      </span>
                    </div>
                  </div>

                  <div className="space-y-3">
                    {result.grants.map((grant, i) => (
                      <GrantCard key={grant.grant_id} grant={grant} index={i} />
                    ))}
                  </div>
                </motion.div>
              )}

              {error && (
                <motion.div
                  key="error"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="glass p-6 text-center"
                >
                  <p className="text-sm text-red-400">{error}</p>
                </motion.div>
              )}

              {!result && !loading && !error && (
                <motion.div
                  key="empty"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="glass p-12 text-center"
                >
                  <div className="mb-4 text-5xl">🔍</div>
                  <p className="text-sm text-white/50">
                    Fill in your project details and click
                    <br />
                    <span className="text-white/70">Find Matching Grants</span>
                  </p>
                </motion.div>
              )}

              {loading && (
                <motion.div
                  key="loading"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="space-y-3"
                >
                  {[...Array(3)].map((_, i) => (
                    <GlassPanel key={i} padding="md" hover={false}>
                      <div className="flex items-start gap-4">
                        <div className="h-14 w-14 shrink-0 animate-pulse rounded-full bg-white/10" />
                        <div className="flex-1 space-y-2">
                          <div className="h-4 w-3/4 animate-pulse rounded-lg bg-white/10" />
                          <div className="h-3 w-1/2 animate-pulse rounded-lg bg-white/[0.06]" />
                          <div className="flex gap-2">
                            <div className="h-5 w-20 animate-pulse rounded-full bg-white/[0.06]" />
                            <div className="h-5 w-16 animate-pulse rounded-full bg-white/[0.06]" />
                          </div>
                        </div>
                      </div>
                    </GlassPanel>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </div>
  )
}
