import type { ApplicantProfile, MatchResponse } from './types'

export async function matchGrants(
  profile: ApplicantProfile
): Promise<MatchResponse> {
  const res = await fetch('/api/match', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(profile),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error((err as { detail?: string; error?: string }).detail ?? (err as { detail?: string; error?: string }).error ?? `Error ${res.status}`)
  }
  return res.json()
}
