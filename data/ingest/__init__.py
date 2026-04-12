"""Shared utilities for all ingestion scripts."""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Sector keyword map — order matters: more specific patterns first
# ---------------------------------------------------------------------------
_SECTOR_PATTERNS: list[tuple[str, str]] = [
    # AI / ML
    (r"\bai\b|machine.learning|deep.learning|neural.network|nlp|computer.vision", "ai"),
    # Healthcare
    (r"health|medical|clinical|nhs|pharma(?!ceutical\s+manufactur)|therapeut|diagnos|patient", "healthcare"),
    # Clean energy
    (r"clean.energy|renewable|solar|wind.power|hydrogen|net.zero|carbon.neutral|decarboni|low.carbon|offshore.wind|bioenergy", "clean_energy"),
    # Manufacturing
    (r"manufactur|industrial|factory|production.line|supply.chain|materials.processing", "manufacturing"),
    # Net zero (distinct enough to keep as its own tag even though it overlaps clean_energy)
    (r"net.zero|carbon.capture|greenhouse.gas|emissions.reduction|climate.target", "net_zero"),
    # Digital / software / cloud
    (r"digital|software|cloud.computing|saas|platform|cybersecurity|cyber.security|information.security|data.security", "digital"),
    # Cybersecurity (also catches digital but we want explicit tag)
    (r"cyber|infosec|penetration.test|zero.trust|encryption", "cybersecurity"),
    # Biotech / genomics / drug discovery
    (r"\bbio(?:tech|logy|informatics|medical|process)\b|genomic|proteom|crispr|synthetic.biology|ferment|drug.discovery|therapeutics?|vaccine", "biotech"),
    # Agritech / food / farming
    (r"agri(?:tech|culture|food)?|food.(?:tech|security|system)|farm(?:ing)?|precision.agriculture|livestock|horticultur", "agritech"),
    # Fintech / finance
    (r"fintech|financ(?:e|ial)|banking|insurtech|payments?|regtech|blockchain.finance", "fintech"),
    # Transport / mobility
    (r"transport|mobility|automotive|electric.vehicle|ev\b|autonomous.vehicle|rail|aviation|maritime|logistics", "transport"),
    # Space / satellite
    (r"\bspace\b|satellite|orbital|launch.vehicle|earth.observation|cubesat", "space"),
    # Quantum
    (r"\bquantum\b", "quantum"),
    # Defence
    (r"\bdefence\b|\bdefense\b|military|dual.use|security.technology|mod\b", "defence"),
    # Education
    (r"educat|learning.platform|e-learning|edtech|skills.training|higher.education", "education"),
    # Climate
    (r"climate.change|climate.adaptation|climate.resilience|flood.risk|extreme.weather", "climate"),
    # Social
    (r"social.enterprise|community|inclusion|equality|wellbeing|mental.health(?!.diagnos)", "social"),
    # Arts / creative
    (r"\barts?\b|creative.industries|cultural|heritage|music.tech|gaming", "arts"),
]

_COMPILED: list[tuple[re.Pattern[str], str]] = [
    (re.compile(pattern, re.IGNORECASE), sector)
    for pattern, sector in _SECTOR_PATTERNS
]


def extract_sectors_from_text(text: str) -> list[str]:
    """
    Scan *text* for sector keywords and return a deduplicated list of
    matching sector tags drawn from the allowed vocabulary.

    Returns an empty list if no keywords match.
    """
    if not text:
        return []
    seen: set[str] = set()
    result: list[str] = []
    for pattern, sector in _COMPILED:
        if sector not in seen and pattern.search(text):
            seen.add(sector)
            result.append(sector)
    return result
