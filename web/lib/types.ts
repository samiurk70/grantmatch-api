export interface ApplicantProfile {
  organisation_name?: string
  organisation_type: OrgType
  description: string
  sectors: Sector[]
  location: Location
  trl?: number
  funding_needed?: number
  top_n?: number
}

export type OrgType =
  'sme' | 'university' | 'charity' | 'large_company' |
  'individual' | 'startup'

export type Sector =
  'ai' | 'healthcare' | 'clean_energy' | 'manufacturing' |
  'digital' | 'biotech' | 'agritech' | 'fintech' | 'net_zero' |
  'transport' | 'space' | 'quantum' | 'cybersecurity' |
  'climate' | 'social' | 'arts' | 'education' | 'other'

export type Location =
  'england' | 'scotland' | 'wales' |
  'northern_ireland' | 'uk' | 'eu'

export type EligibilityVerdict =
  'likely_eligible' | 'check_required' | 'likely_ineligible'

export interface FactorExplanation {
  factor_name: string
  direction: 'positive' | 'negative'
  impact: number
}

export interface GrantMatch {
  grant_id: number
  title: string
  funder: string
  programme?: string
  summary: string
  score: number
  confidence: number
  deadline?: string
  status: string
  funding_range: string
  eligibility_verdict: EligibilityVerdict
  top_factors: FactorExplanation[]
  url?: string
}

export interface MatchResponse {
  profile_summary: string
  total_matched: number
  grants: GrantMatch[]
  processing_time_ms: number
  data_freshness: string
}
