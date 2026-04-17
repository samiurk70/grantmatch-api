'use client'
import { useState } from 'react'
import { motion } from 'framer-motion'
import { Loader2, Sparkles } from 'lucide-react'
import { GlassPanel } from '@/components/shared/GlassPanel'
import {
  ORG_TYPE_LABELS,
  SECTOR_LABELS,
  LOCATION_LABELS,
  TRL_LABELS,
} from '@/lib/constants'
import type { ApplicantProfile, OrgType, Sector, Location } from '@/lib/types'

interface SearchFormProps {
  onSearch: (profile: ApplicantProfile) => void
  loading: boolean
}

export function SearchForm({ onSearch, loading }: SearchFormProps) {
  const [description, setDescription] = useState('')
  const [orgType, setOrgType] = useState<OrgType>('sme')
  const [sectors, setSectors] = useState<Sector[]>([])
  const [location, setLocation] = useState<Location>('england')
  const [trl, setTrl] = useState(4)
  const [fundingNeeded, setFundingNeeded] = useState('')

  const toggleSector = (s: Sector) => {
    setSectors(prev =>
      prev.includes(s) ? prev.filter(x => x !== s) : [...prev, s]
    )
  }

  const handleSubmit = () => {
    if (description.length < 50 || sectors.length === 0) return
    onSearch({
      organisation_type: orgType,
      description,
      sectors,
      location,
      trl,
      funding_needed: fundingNeeded ? Number(fundingNeeded) : undefined,
      top_n: 10,
    })
  }

  const valid = description.length >= 50 && sectors.length > 0

  return (
    <GlassPanel padding="lg" hover={false} className="space-y-5">
      {/* Description */}
      <div>
        <label className="mb-2 block text-sm text-white/70">
          Describe your project
          <span className="ml-2 text-xs text-white/40">
            ({description.length}/50 min)
          </span>
        </label>
        <textarea
          value={description}
          onChange={e => setDescription(e.target.value)}
          placeholder="What are you building? What problem does it solve? What stage are you at?"
          rows={4}
          className="min-h-[80px] w-full resize-none rounded-xl border border-white/[0.12] bg-white/5
            px-4 py-3 text-sm text-white/90 placeholder-white/30 transition-all
            duration-200 focus:border-blue-500/50 focus:bg-white/[0.08] focus:outline-none
            md:min-h-[100px]"
        />
      </div>

      {/* Org type + Location row */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <label className="mb-1.5 block text-xs text-white/50">
            Organisation type
          </label>
          <select
            value={orgType}
            onChange={e => setOrgType(e.target.value as OrgType)}
            className="w-full rounded-xl border border-white/[0.12] bg-white/5
              px-3 py-2.5 text-sm text-white/90 transition-all duration-200
              focus:border-blue-500/50 focus:outline-none"
          >
            {Object.entries(ORG_TYPE_LABELS).map(([v, l]) => (
              <option key={v} value={v} className="bg-[#0a0f1e] text-white">
                {l}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="mb-1.5 block text-xs text-white/50">
            Location
          </label>
          <select
            value={location}
            onChange={e => setLocation(e.target.value as Location)}
            className="w-full rounded-xl border border-white/[0.12] bg-white/5
              px-3 py-2.5 text-sm text-white/90 transition-all duration-200
              focus:border-blue-500/50 focus:outline-none"
          >
            {Object.entries(LOCATION_LABELS).map(([v, l]) => (
              <option key={v} value={v} className="bg-[#0a0f1e] text-white">
                {l}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Sectors */}
      <div>
        <label className="mb-2 block text-xs text-white/50">
          Sectors{' '}
          <span className="text-white/30">(select all that apply)</span>
        </label>
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(SECTOR_LABELS).map(([v, l]) => {
            const active = sectors.includes(v as Sector)
            return (
              <button
                key={v}
                type="button"
                onClick={() => toggleSector(v as Sector)}
                className={`min-h-[36px] rounded-full border px-3 py-1 text-xs transition-all duration-200
                  ${
                    active
                      ? 'border-blue-500/50 bg-blue-500/25 text-blue-300'
                      : 'border-white/[0.12] bg-white/5 text-white/50 hover:bg-white/10 hover:text-white/70'
                  }`}
              >
                {l}
              </button>
            )
          })}
        </div>
      </div>

      {/* TRL slider */}
      <div>
        <label className="mb-2 block text-xs text-white/50">
          Technology Readiness Level (TRL):{' '}
          <span className="text-white/80">
            {trl} — {TRL_LABELS[trl]}
          </span>
        </label>
        <input
          type="range"
          min={1}
          max={9}
          value={trl}
          onChange={e => setTrl(Number(e.target.value))}
          className="w-full cursor-pointer accent-blue-500"
        />
        <div className="mt-1 flex justify-between text-xs text-white/25">
          <span>1 Basic</span>
          <span>9 Proven</span>
        </div>
      </div>

      {/* Funding needed */}
      <div>
        <label className="mb-1.5 block text-xs text-white/50">
          Approximate funding needed (£, optional)
        </label>
        <input
          type="number"
          value={fundingNeeded}
          onChange={e => setFundingNeeded(e.target.value)}
          placeholder="e.g. 250000"
          className="w-full rounded-xl border border-white/[0.12] bg-white/5
            px-3 py-2.5 text-sm text-white/90 placeholder-white/30 transition-all
            duration-200 focus:border-blue-500/50 focus:outline-none"
        />
      </div>

      {/* Submit */}
      <motion.button
        onClick={handleSubmit}
        disabled={!valid || loading}
        whileHover={{ scale: valid && !loading ? 1.02 : 1 }}
        whileTap={{ scale: valid && !loading ? 0.98 : 1 }}
        className={`flex w-full items-center justify-center gap-2 rounded-xl
          py-3.5 text-sm font-semibold transition-all duration-300
          ${
            valid && !loading
              ? `bg-gradient-to-r from-blue-600 to-blue-500
                 text-white shadow-[0_0_30px_rgba(79,142,247,0.35)]
                 hover:from-blue-500 hover:to-blue-400
                 hover:shadow-[0_0_40px_rgba(79,142,247,0.5)]`
              : 'cursor-not-allowed bg-white/[0.08] text-white/30'
          }`}
      >
        {loading ? (
          <>
            <Loader2 size={16} className="animate-spin" />
            Searching 24,699 grants...
          </>
        ) : (
          <>
            <Sparkles size={16} />
            Find Matching Grants
          </>
        )}
      </motion.button>

      {description.length > 0 && description.length < 50 && (
        <p className="-mt-2 text-center text-xs text-amber-400/80">
          Add {50 - description.length} more characters to your description
        </p>
      )}
    </GlassPanel>
  )
}
