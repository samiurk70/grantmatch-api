export const ORG_TYPE_LABELS: Record<string, string> = {
  sme: 'SME (Small/Medium Business)',
  startup: 'Startup',
  university: 'University / Research Organisation',
  charity: 'Charity / Non-Profit',
  large_company: 'Large Company',
  individual: 'Individual / Freelancer',
}

export const SECTOR_LABELS: Record<string, string> = {
  ai: 'AI & Machine Learning',
  healthcare: 'Healthcare & Life Sciences',
  clean_energy: 'Clean Energy',
  manufacturing: 'Manufacturing',
  digital: 'Digital & Software',
  biotech: 'Biotech & Genomics',
  agritech: 'AgriTech & Food',
  fintech: 'FinTech',
  net_zero: 'Net Zero & Sustainability',
  transport: 'Transport & Mobility',
  space: 'Space & Satellites',
  quantum: 'Quantum Technology',
  cybersecurity: 'Cybersecurity',
  climate: 'Climate & Environment',
  social: 'Social Enterprise',
  education: 'Education & Skills',
  arts: 'Arts & Culture',
  other: 'Other',
}

export const LOCATION_LABELS: Record<string, string> = {
  england: 'England',
  scotland: 'Scotland',
  wales: 'Wales',
  northern_ireland: 'Northern Ireland',
  uk: 'UK-wide',
  eu: 'EU / International',
}

export const TRL_LABELS: Record<number, string> = {
  1: 'Basic research',
  2: 'Technology concept',
  3: 'Experimental proof',
  4: 'Lab validation',
  5: 'Relevant environment',
  6: 'Demo environment',
  7: 'Operational prototype',
  8: 'Complete & qualified',
  9: 'Proven in operation',
}
