"""
Train an XGBoost reranker on synthetic (grant, profile) pairs.

Usage:
    python ml/train.py

Outputs:
    ml/model.pkl  — trained XGBClassifier, loadable by app/services/reranker.py
    Console       — accuracy, macro-F1, per-class precision/recall
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import joblib
import numpy as np
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

# Ensure project root is on sys.path when run as a script
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.utils.feature_extractor import FEATURE_NAMES, extract_features  # noqa: E402
from app.services.embedder import get_embedder  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_NOW = datetime.utcnow()
_90_DAYS = _NOW + timedelta(days=90)
_180_DAYS = _NOW + timedelta(days=180)
_PAST = _NOW - timedelta(days=30)

MODEL_OUT = _ROOT / "ml" / "model.pkl"

# ---------------------------------------------------------------------------
# Synthetic grant pool — 30 records
# ---------------------------------------------------------------------------

def _grant(
    title: str,
    funder: str,
    description: str,
    status: str,
    deadline,
    org_types,
    regions,
    trl,
    sectors,
    funding_min: float,
    funding_max: float,
) -> SimpleNamespace:
    return SimpleNamespace(
        title=title,
        funder=funder,
        description=description,
        status=status,
        deadline=deadline,
        eligibility_org_types=org_types,
        eligibility_regions=regions,
        eligibility_trl=trl,
        eligibility_sectors=sectors,
        funding_min=funding_min,
        funding_max=funding_max,
    )


GRANTS: list[SimpleNamespace] = [
    # ------------------------------------------------------------------ #
    # 1-5: Innovate UK — AI / digital (SME, TRL 4-7, UK)
    # ------------------------------------------------------------------ #
    _grant(
        "Innovate UK AI Innovation Fund — Round 1",
        "Innovate UK",
        "Funding for small and medium enterprises developing AI-based solutions that "
        "address productivity challenges in UK industries. Projects must demonstrate "
        "a clear route to market and commercial viability.",
        "open", _90_DAYS,
        ["sme", "startup"], ["uk"], [4, 7], ["ai", "digital"],
        50_000, 300_000,
    ),
    _grant(
        "Innovate UK Digital Catapult Seed Grant",
        "Innovate UK",
        "Early-stage funding for digital product startups building scalable software "
        "platforms. Focus on UK market and B2B applications using modern AI/ML techniques.",
        "open", _180_DAYS,
        ["sme", "startup"], ["uk"], [4, 6], ["ai", "digital", "fintech"],
        25_000, 150_000,
    ),
    _grant(
        "AI for Business Transformation Grant",
        "Innovate UK",
        "Supporting UK SMEs adopting artificial intelligence and machine learning to "
        "transform internal processes, reduce costs, and improve customer outcomes.",
        "open", _90_DAYS,
        ["sme"], ["england", "scotland", "wales"], [5, 7], ["ai", "digital"],
        75_000, 500_000,
    ),
    _grant(
        "Smart Data Challenge Fund",
        "Innovate UK",
        "Grants for businesses developing data-driven digital services that leverage "
        "open datasets and AI analysis to create new products or improve existing services.",
        "upcoming", _180_DAYS,
        ["sme", "startup"], ["uk"], [4, 7], ["digital", "ai", "fintech"],
        50_000, 250_000,
    ),
    _grant(
        "Innovate UK Cyber Innovation Grant",
        "Innovate UK",
        "Backing SMEs developing cyber security products and services for UK critical "
        "national infrastructure and commercial sectors. Emphasis on AI-driven threat detection.",
        "open", _90_DAYS,
        ["sme", "startup"], ["uk"], [4, 8], ["cybersecurity", "ai", "digital"],
        100_000, 500_000,
    ),
    # ------------------------------------------------------------------ #
    # 6-10: UKRI research grants (university, TRL 1-4, UK)
    # ------------------------------------------------------------------ #
    _grant(
        "EPSRC Doctoral Training Partnership",
        "EPSRC / UKRI",
        "Funding for PhD studentships in engineering and physical sciences. "
        "Universities lead collaborative research programmes addressing fundamental "
        "challenges in digital technologies and AI.",
        "open", _180_DAYS,
        ["university"], ["uk"], [1, 3], ["ai", "quantum", "digital"],
        100_000, 2_000_000,
    ),
    _grant(
        "BBSRC Strategic Longer and Larger Grant",
        "BBSRC / UKRI",
        "Large grants for world-class bioscience research programmes in UK universities. "
        "Funds interdisciplinary teams working on transformative challenges in biology, "
        "agriculture, and food security.",
        "open", _180_DAYS,
        ["university"], ["uk"], [1, 4], ["biotech", "agritech", "healthcare"],
        500_000, 2_000_000,
    ),
    _grant(
        "MRC Research Grant — Biomedical Sciences",
        "MRC / UKRI",
        "Supporting fundamental and applied research in biomedical sciences at UK "
        "universities. Priorities include genomics, drug discovery, and translational "
        "medicine.",
        "open", _90_DAYS,
        ["university"], ["uk"], [1, 4], ["healthcare", "biotech"],
        150_000, 1_500_000,
    ),
    _grant(
        "NERC Environmental Research Grant",
        "NERC / UKRI",
        "Funding for environmental science research at UK universities. Current focus "
        "areas include climate modelling, net-zero pathways, biodiversity, and sustainable "
        "land use.",
        "open", _180_DAYS,
        ["university"], ["uk"], [1, 3], ["climate", "net_zero", "agritech"],
        100_000, 1_000_000,
    ),
    _grant(
        "AHRC Creative Industries R&D Fund",
        "AHRC / UKRI",
        "Research and development funding for universities partnering with creative "
        "industries. Topics include digital arts, cultural heritage preservation, and "
        "interactive media.",
        "open", _180_DAYS,
        ["university"], ["uk"], [1, 4], ["arts", "digital", "education"],
        75_000, 800_000,
    ),
    # ------------------------------------------------------------------ #
    # 11-15: Horizon Europe tech grants (any org, EU+UK)
    # ------------------------------------------------------------------ #
    _grant(
        "Horizon Europe EIC Accelerator — DeepTech",
        "European Innovation Council",
        "Pan-European funding for breakthrough deep technology companies and startups. "
        "Focus on AI, quantum computing, advanced materials, and biotechnology with "
        "strong commercial potential and societal impact.",
        "open", _90_DAYS,
        ["sme", "startup"], ["eu", "uk"], [5, 9], ["ai", "quantum", "biotech"],
        500_000, 2_500_000,
    ),
    _grant(
        "Horizon Europe ERC Advanced Grant",
        "European Research Council",
        "Prestigious grants for senior researchers at EU or associated country institutions "
        "conducting frontier research in any field. UK institutions eligible under Horizon "
        "Association Agreement.",
        "open", _180_DAYS,
        ["university"], ["eu", "uk"], [1, 4], ["ai", "biotech", "climate", "quantum"],
        1_000_000, 2_500_000,
    ),
    _grant(
        "Horizon Europe Cluster 4 — Digital Technologies",
        "European Commission",
        "Collaborative R&I projects across European consortia focusing on next-generation "
        "internet, AI, cybersecurity, and advanced digital technologies for industry.",
        "open", _90_DAYS,
        None, ["eu", "uk"], [3, 7], ["digital", "ai", "cybersecurity", "quantum"],
        1_000_000, 5_000_000,
    ),
    _grant(
        "Horizon Europe Cluster 6 — Food, Bioeconomy and Environment",
        "European Commission",
        "Funding for research and innovation in sustainable agriculture, forestry, "
        "marine and maritime research. Addresses climate change, biodiversity loss, "
        "and the European Green Deal.",
        "open", _180_DAYS,
        None, ["eu", "uk"], [2, 6], ["agritech", "climate", "net_zero", "biotech"],
        800_000, 4_000_000,
    ),
    _grant(
        "Horizon Europe EIC Pathfinder — Advanced Research",
        "European Innovation Council",
        "Support for high-risk, high-reward research exploring radically new technologies. "
        "Welcomes interdisciplinary proposals at the intersection of physics, biology, "
        "and computer science.",
        "open", _90_DAYS,
        None, ["eu", "uk"], [1, 3], ["quantum", "ai", "biotech", "space"],
        500_000, 3_000_000,
    ),
    # ------------------------------------------------------------------ #
    # 16-20: Clean energy grants (SME+university, TRL 3-8, UK)
    # ------------------------------------------------------------------ #
    _grant(
        "Net Zero Innovation Portfolio — Low Carbon Heat",
        "DESNZ / BEIS",
        "Grants for innovators developing low-carbon heat technologies including heat "
        "pumps, district heating systems, and hydrogen boilers. Targets UK homes and "
        "commercial buildings.",
        "open", _90_DAYS,
        ["sme", "university"], ["uk"], [3, 8], ["clean_energy", "net_zero"],
        100_000, 750_000,
    ),
    _grant(
        "UKRI Supergen Energy Networks Hub",
        "EPSRC / UKRI",
        "Research into future energy networks, smart grid technologies, and integration "
        "of renewables. Academic-industry collaboration to accelerate the energy transition "
        "in the UK.",
        "open", _180_DAYS,
        ["university", "sme"], ["uk"], [3, 7], ["clean_energy", "net_zero", "digital"],
        200_000, 1_000_000,
    ),
    _grant(
        "Offshore Wind Growth Partnership Fund",
        "Crown Estate / Innovate UK",
        "Supporting UK supply chain companies developing innovative components and "
        "services for offshore wind energy. Focus on cost reduction and reliability "
        "improvements.",
        "open", _90_DAYS,
        ["sme", "large_company"], ["england", "scotland"], [4, 8],
        ["clean_energy", "net_zero", "manufacturing"],
        150_000, 1_000_000,
    ),
    _grant(
        "Hydrogen Transport Innovation Fund",
        "Department for Transport",
        "Funding for development and demonstration of hydrogen-powered transport "
        "solutions in the UK, including fuel cells, storage systems, and refuelling "
        "infrastructure.",
        "open", _180_DAYS,
        ["sme", "large_company", "university"], ["uk"], [4, 8],
        ["clean_energy", "transport", "net_zero"],
        200_000, 1_000_000,
    ),
    _grant(
        "Energy Entrepreneurs Fund",
        "DESNZ",
        "Supporting innovative UK businesses developing novel energy storage, generation "
        "and efficiency technologies. Seed-stage to scale-up funding for clean energy "
        "entrepreneurs.",
        "open", _90_DAYS,
        ["sme", "startup"], ["uk"], [3, 7], ["clean_energy", "net_zero"],
        100_000, 500_000,
    ),
    # ------------------------------------------------------------------ #
    # 21-25: Healthcare grants (SME+university, TRL 2-6, UK+EU)
    # ------------------------------------------------------------------ #
    _grant(
        "NIHR Invention for Innovation Programme",
        "NIHR",
        "Funding for applied health and care research leading to new diagnostic and "
        "therapeutic devices or products. Supports NHS clinical validation and "
        "commercialisation pathways for UK innovators.",
        "open", _90_DAYS,
        ["sme", "university"], ["uk"], [2, 6], ["healthcare", "biotech"],
        100_000, 500_000,
    ),
    _grant(
        "UKRI Biomedical Catalyst",
        "MRC / Innovate UK",
        "Accelerating UK healthcare innovation from discovery to commercial application. "
        "Supports academic spinouts and SMEs developing medical technologies, diagnostics, "
        "and therapeutics.",
        "open", _90_DAYS,
        ["sme", "university", "startup"], ["uk"], [2, 6],
        ["healthcare", "biotech", "ai"],
        100_000, 2_000_000,
    ),
    _grant(
        "Wellcome Trust Innovator Awards",
        "Wellcome Trust",
        "Backing scientists and clinicians with bold ideas to transform human and "
        "animal health. Supports early-stage proof-of-concept through to clinical "
        "trials and scaling.",
        "open", _180_DAYS,
        ["university", "sme"], ["uk", "eu"], [1, 5], ["healthcare", "biotech"],
        250_000, 2_000_000,
    ),
    _grant(
        "Innovate UK Digital Health Technology Catalyst",
        "Innovate UK",
        "Grants for UK companies developing digital health technologies, including "
        "AI diagnostics, remote monitoring, mental health apps, and electronic patient "
        "record solutions.",
        "open", _90_DAYS,
        ["sme", "startup"], ["uk"], [3, 6], ["healthcare", "ai", "digital"],
        50_000, 500_000,
    ),
    _grant(
        "EU Health4EU Collaborative Research Grant",
        "EU4Health Programme",
        "European collaborative funding for public health research, disease prevention, "
        "and health system strengthening. Open to consortia across EU and associated "
        "countries.",
        "open", _180_DAYS,
        None, ["eu", "uk"], [2, 5], ["healthcare", "biotech", "digital"],
        500_000, 2_000_000,
    ),
    # ------------------------------------------------------------------ #
    # 26-30: GOV.UK social / charity grants (charity+individual, UK)
    # ------------------------------------------------------------------ #
    _grant(
        "National Lottery Community Fund — Small Grants",
        "National Lottery Community Fund",
        "Small grants for community groups and voluntary organisations delivering "
        "projects that bring people together, improve wellbeing, and support "
        "disadvantaged communities across the UK.",
        "open", _90_DAYS,
        ["charity", "individual"], ["uk"], None,
        ["social", "education"],
        5_000, 10_000,
    ),
    _grant(
        "Arts Council England — Project Grants",
        "Arts Council England",
        "Supporting individual artists, community groups, and arts organisations in "
        "England to create and share art. Funds productions, exhibitions, residencies, "
        "and community arts projects.",
        "open", _90_DAYS,
        ["charity", "individual"], ["england"], None,
        ["arts", "education", "social"],
        1_000, 30_000,
    ),
    _grant(
        "Big Lottery Fund — Local Connections Fund",
        "National Lottery Community Fund",
        "Funding for small charities and community organisations to build connections "
        "and increase participation in social activities. Targets isolated groups and "
        "deprived communities.",
        "open", _180_DAYS,
        ["charity"], ["uk"], None,
        ["social", "education"],
        5_000, 25_000,
    ),
    _grant(
        "Comic Relief UK Grants — Education and Young People",
        "Comic Relief",
        "Grants for UK charities and not-for-profits addressing educational inequality, "
        "youth unemployment, and skills development for young people from disadvantaged "
        "backgrounds.",
        "open", _90_DAYS,
        ["charity"], ["uk"], None,
        ["education", "social"],
        10_000, 50_000,
    ),
    _grant(
        "Sport England — Together Fund",
        "Sport England",
        "Funding for community organisations to increase physical activity and sport "
        "participation across England. Targets underrepresented groups including women, "
        "disabled people, and lower socioeconomic communities.",
        "open", _180_DAYS,
        ["charity", "individual"], ["england"], None,
        ["social", "education"],
        5_000, 50_000,
    ),
]

assert len(GRANTS) == 30, f"Expected 30 grants, got {len(GRANTS)}"

# ---------------------------------------------------------------------------
# Synthetic profile pool — 50 profiles
# ---------------------------------------------------------------------------

from app.models.schemas import ApplicantProfile  # noqa: E402

_LONG_DESC = {
    "ai_sme": (
        "We are developing an AI-powered platform that uses machine learning and natural "
        "language processing to automate business intelligence reporting for SMEs. Our "
        "solution reduces analyst time by 80% while improving data accuracy and insight quality."
    ),
    "ai_digital": (
        "Building a next-generation AI recommendation engine for e-commerce and digital "
        "media platforms. Our deep learning models personalise user experiences in real time "
        "and have demonstrated 35% uplift in conversion rates during pilot trials."
    ),
    "biotech_uni": (
        "University research group investigating novel CRISPR-based gene editing approaches "
        "for treating rare genetic disorders. Our work bridges computational biology and wet "
        "lab experimentation to identify therapeutic targets."
    ),
    "healthcare_startup": (
        "We are a health technology startup developing an AI diagnostic tool for early "
        "detection of diabetic retinopathy using smartphone cameras. Our algorithm achieves "
        "clinician-level accuracy at a fraction of the cost of traditional screening."
    ),
    "clean_energy_sme": (
        "Our company designs and manufactures advanced battery management systems for "
        "grid-scale energy storage installations. We are working to reduce levelised cost "
        "of storage and improve cycle life for utility-scale deployments."
    ),
    "net_zero_uni": (
        "Research team modelling carbon capture and storage pathways for the UK net-zero "
        "transition. We combine atmospheric chemistry, geological surveys, and economic "
        "modelling to evaluate viable sequestration sites and policy options."
    ),
    "agritech_sme": (
        "Precision agriculture startup deploying drone-based multispectral imaging and AI "
        "analytics to help UK farmers monitor crop health, optimise irrigation, and reduce "
        "pesticide use. Demonstrated 20% yield improvement in field trials."
    ),
    "fintech_sme": (
        "Building an open banking platform that uses AI to provide real-time credit scoring "
        "and personalised financial advice for underserved consumers. FCA-registered and "
        "compliant with PSD2 regulations."
    ),
    "cybersecurity_sme": (
        "Our cybersecurity firm develops AI-driven threat intelligence and automated incident "
        "response tools for critical national infrastructure operators. We detect novel attack "
        "patterns that signature-based tools miss."
    ),
    "quantum_uni": (
        "Theoretical and experimental research into quantum error correction codes and "
        "fault-tolerant quantum computing architectures. Collaborating with industry partners "
        "to bridge the gap between current noisy intermediate-scale quantum devices and "
        "practical fault-tolerant machines."
    ),
    "social_charity": (
        "Community interest company running employment support programmes for long-term "
        "unemployed adults in deprived urban areas. Our personalised coaching model has "
        "helped over 500 people into sustained work in the past two years."
    ),
    "arts_individual": (
        "Independent theatre company creating accessible arts experiences for communities "
        "with limited access to cultural venues. We tour productions to schools, care homes, "
        "and community centres across rural England."
    ),
    "manufacturing_sme": (
        "Advanced manufacturing SME developing robotic automation systems for food processing "
        "lines. Our vision-guided robots reduce waste by 15% and increase throughput while "
        "meeting strict food safety hygiene standards."
    ),
    "transport_startup": (
        "Startup developing hydrogen fuel cell range extenders for commercial electric "
        "vehicles including vans and buses. Our modular system integrates with existing EV "
        "platforms and extends range to over 600 miles."
    ),
    "space_sme": (
        "Small satellite communications company building low Earth orbit constellations for "
        "IoT and broadband connectivity. Our proprietary antenna technology and orbital "
        "insertion system dramatically reduces launch costs."
    ),
    "education_charity": (
        "Education charity delivering digital literacy and coding programmes in primary "
        "schools serving deprived communities. We train teachers and provide curriculum "
        "materials aligned with the national computing curriculum."
    ),
    "defence_large": (
        "Defence technology company developing autonomous surveillance systems using AI "
        "and computer vision for border monitoring and critical infrastructure protection. "
        "Working under MOD contract with NATO interoperability requirements."
    ),
    "climate_uni": (
        "Environmental science research group studying feedback mechanisms in Arctic "
        "permafrost thaw and their contribution to atmospheric methane levels. We use "
        "satellite remote sensing combined with in-field sensor networks."
    ),
    "biotech_eu": (
        "Biotechnology company in the EU developing mRNA vaccine platforms for infectious "
        "disease prevention. Our modular design allows rapid adaptation to new pathogens "
        "and is compatible with standard cold chain logistics."
    ),
    "healthcare_eu": (
        "Pan-European consortium researching AI-assisted surgical robotics for minimally "
        "invasive procedures. Bringing together clinical partners, robotics engineers, and "
        "computer vision researchers across five countries."
    ),
    "digital_university": (
        "University research centre studying human-computer interaction and the social "
        "impacts of AI deployment in public sector services. We conduct mixed-method "
        "research combining user studies and algorithmic auditing."
    ),
    "ai_university": (
        "Machine learning research group developing interpretable AI methods for high-stakes "
        "decision making in healthcare and criminal justice. Our work focuses on fairness, "
        "accountability, and transparency in algorithmic systems."
    ),
    "net_zero_sme": (
        "SME developing smart building energy management software that uses AI to optimise "
        "heating, ventilation, and air conditioning systems. Proven to reduce energy bills "
        "by 30% in commercial buildings."
    ),
    "social_large": (
        "Large social enterprise delivering integrated employment, housing, and mental health "
        "support services for vulnerable adults. We operate across ten local authority areas "
        "and partner with NHS trusts."
    ),
    "startup_ai_eu": (
        "Deep tech startup based in Berlin developing foundation models for scientific "
        "discovery in drug design and materials science. Our generative AI models accelerate "
        "hit identification and reduce experimental costs."
    ),
}


def _profile(
    org_name: str,
    org_type: str,
    description_key: str,
    sectors: list[str],
    location: str,
    trl: int | None,
    funding_needed: float | None = None,
) -> ApplicantProfile:
    return ApplicantProfile(
        organisation_name=org_name,
        organisation_type=org_type,
        description=_LONG_DESC[description_key],
        sectors=sectors,
        location=location,
        trl=trl,
        funding_needed=funding_needed,
    )


PROFILES: list[ApplicantProfile] = [
    # --- AI / digital SMEs ---
    _profile("NeuralOps Ltd",      "sme",         "ai_sme",            ["ai", "digital"],           "uk",              5, 200_000),
    _profile("DeepStack Ltd",      "startup",     "ai_digital",        ["ai", "digital"],           "england",         6, 100_000),
    _profile("AlgoSense Ltd",      "sme",         "ai_sme",            ["ai"],                      "scotland",        4, 150_000),
    _profile("CogniFlow Ltd",      "startup",     "ai_digital",        ["ai", "fintech"],           "uk",              5, 75_000),
    _profile("SecureAI Ltd",       "sme",         "cybersecurity_sme", ["cybersecurity", "ai"],     "england",         6, 250_000),
    # --- University AI / digital ---
    _profile("Oxford AI Lab",      "university",  "ai_university",     ["ai", "digital"],           "england",         2, None),
    _profile("Edinburgh ML Group", "university",  "ai_university",     ["ai", "quantum"],           "scotland",        3, None),
    _profile("UCL HCI Centre",     "university",  "digital_university",["digital", "education"],    "england",         2, None),
    # --- Biotech / healthcare ---
    _profile("GenEdit Bio",        "startup",     "biotech_uni",       ["biotech", "healthcare"],   "uk",              3, 300_000),
    _profile("RetinaAI Ltd",       "startup",     "healthcare_startup",["healthcare", "ai"],        "england",         4, 150_000),
    _profile("Cambridge Genomics", "university",  "biotech_uni",       ["biotech", "healthcare"],   "uk",              2, None),
    _profile("MRC Translational",  "university",  "biotech_uni",       ["biotech"],                 "england",         3, None),
    _profile("MedTech Diagnostics","sme",         "healthcare_startup",["healthcare", "ai"],        "uk",              5, 200_000),
    _profile("VaccineCo EU",       "sme",         "biotech_eu",        ["biotech", "healthcare"],   "eu",              4, 500_000),
    _profile("SurgBot Consortium", "university",  "healthcare_eu",     ["healthcare", "ai"],        "eu",              4, None),
    # --- Clean energy ---
    _profile("GridStore Energy",   "sme",         "clean_energy_sme",  ["clean_energy", "net_zero"],"uk",              6, 300_000),
    _profile("CarbonPath Ltd",     "university",  "net_zero_uni",      ["net_zero", "climate"],     "uk",              3, None),
    _profile("WindTech UK",        "sme",         "clean_energy_sme",  ["clean_energy"],            "scotland",        7, 500_000),
    _profile("H2Drive Ltd",        "startup",     "transport_startup", ["transport", "clean_energy"],"england",        5, 200_000),
    _profile("SmartBuildings Ltd", "sme",         "net_zero_sme",      ["net_zero", "digital"],     "england",         5, 150_000),
    # --- Agritech ---
    _profile("CropView Ltd",       "sme",         "agritech_sme",      ["agritech", "ai"],          "england",         4, 100_000),
    _profile("SoilSense Ltd",      "startup",     "agritech_sme",      ["agritech"],                "wales",           3, 75_000),
    _profile("Rothamsted Partner", "university",  "biotech_uni",       ["agritech", "biotech"],     "england",         2, None),
    # --- Quantum ---
    _profile("QuantumCo Ltd",      "sme",         "quantum_uni",       ["quantum", "digital"],      "uk",              3, 400_000),
    _profile("UCL Quantum Hub",    "university",  "quantum_uni",       ["quantum", "ai"],           "england",         2, None),
    # --- Fintech ---
    _profile("OpenCredit Ltd",     "startup",     "fintech_sme",       ["fintech", "ai"],           "england",         5, 100_000),
    _profile("PayFlow Ltd",        "sme",         "fintech_sme",       ["fintech", "digital"],      "uk",              6, 200_000),
    # --- Space / defence ---
    _profile("OrbitSat Ltd",       "sme",         "space_sme",         ["space", "digital"],        "uk",              6, 300_000),
    _profile("DefenceAI Ltd",      "large_company","defence_large",    ["defence", "ai"],           "england",         7, 1_000_000),
    # --- Social / charity ---
    _profile("Community Works CIC","charity",     "social_charity",    ["social", "education"],     "england",         None, 20_000),
    _profile("Pathways Trust",     "charity",     "social_charity",    ["social"],                  "scotland",        None, 15_000),
    _profile("StageWorks Theatre", "individual",  "arts_individual",   ["arts", "social"],          "england",         None, 10_000),
    _profile("DigitalLearn CIC",   "charity",     "education_charity", ["education", "digital"],    "uk",              None, 30_000),
    _profile("SportActive Ltd",    "charity",     "social_charity",    ["social"],                  "england",         None, 25_000),
    # --- Climate ---
    _profile("Arctic Research Grp","university",  "climate_uni",       ["climate", "net_zero"],     "uk",              2, None),
    _profile("EcoAnalytics Ltd",   "sme",         "net_zero_sme",      ["climate", "clean_energy"], "uk",              4, 100_000),
    # --- Manufacturing ---
    _profile("RoboFood Ltd",       "sme",         "manufacturing_sme", ["manufacturing", "ai"],     "england",         6, 250_000),
    _profile("AutoLine Ltd",       "large_company","manufacturing_sme",["manufacturing"],           "england",         7, 500_000),
    # --- Education ---
    _profile("EduCode CIC",        "charity",     "education_charity", ["education"],               "uk",              None, 40_000),
    _profile("FutureSkills Ltd",   "sme",         "education_charity", ["education", "digital"],    "england",         None, 50_000),
    # --- EU tech / cross-border ---
    _profile("Berlin DeepTech",    "startup",     "startup_ai_eu",     ["ai", "biotech"],           "eu",              3, 1_000_000),
    _profile("MedResearch EU",     "university",  "healthcare_eu",     ["healthcare", "digital"],   "eu",              3, None),
    # --- Mixed / edge profiles ---
    _profile("ClimateAI Ltd",      "sme",         "net_zero_sme",      ["ai", "climate", "net_zero"],"uk",             5, 200_000),
    _profile("Biodigital Ltd",     "startup",     "biotech_eu",        ["biotech", "digital", "ai"],"uk",              4, 350_000),
    _profile("ArtsTech Ltd",       "sme",         "arts_individual",   ["arts", "digital"],         "england",         None, 20_000),
    _profile("SocialAI Ltd",       "charity",     "social_charity",    ["social", "ai"],            "uk",              None, 30_000),
    _profile("HealthQuantum Ltd",  "university",  "quantum_uni",       ["healthcare", "quantum"],   "uk",              3, None),
    _profile("TransportNet Ltd",   "large_company","transport_startup", ["transport", "net_zero"],   "uk",              7, 800_000),
    _profile("CyberDefence Ltd",   "sme",         "defence_large",     ["defence", "cybersecurity"],"england",         7, 400_000),
    _profile("NorthernSME Ltd",    "sme",         "ai_sme",            ["ai", "manufacturing"],     "northern_ireland",5, 120_000),
]

assert len(PROFILES) == 50, f"Expected 50 profiles, got {len(PROFILES)}"


# ---------------------------------------------------------------------------
# Label generation
# ---------------------------------------------------------------------------

def _location_compatible(profile_location: str, grant_regions: list | None) -> bool:
    if not grant_regions:
        return True
    _UK = frozenset(["uk", "england", "scotland", "wales", "northern_ireland"])
    regions = set(grant_regions)
    if "international" in regions or profile_location in regions:
        return True
    if "uk" in regions and profile_location in _UK:
        return True
    if profile_location == "uk" and regions & _UK:
        return True
    return False


def _assign_label(
    grant: SimpleNamespace,
    profile: ApplicantProfile,
    semantic_sim: float,
) -> int:
    """
    Assign a relevance label (0–3) to a (grant, profile) pair.

    Three primary eligibility dimensions:
      org_match    — grant accepts this org type (or has no restriction)
      region_match — grant covers the applicant's location
      sector_match — grant sectors overlap the applicant's sectors
                     (grants with no sector restriction are a soft match)

    key_dims = sum of the three booleans above.

      Label 3 (strong):    key_dims == 3, TRL in range, semantic_sim > 0.4
      Label 2 (good):      key_dims == 3
      Label 1 (weak):      key_dims == 2  (one dimension misses)
      Label 0 (irrelevant):key_dims <= 1  (two or more dimensions miss)

    Target distribution: ~40% / ~35% / ~20% / ~5% (0/1/2/3).
    """
    org_match = (
        not grant.eligibility_org_types
        or profile.organisation_type in grant.eligibility_org_types
    )
    region_match = _location_compatible(profile.location, grant.eligibility_regions)

    grant_sectors = set(grant.eligibility_sectors or [])
    profile_sectors = set(profile.sectors)
    # If the grant has no sector restriction, treat as a soft sector match
    sector_match = (not grant_sectors) or bool(profile_sectors & grant_sectors)

    trl_match = True
    if grant.eligibility_trl and profile.trl is not None:
        trl_match = grant.eligibility_trl[0] <= profile.trl <= grant.eligibility_trl[-1]

    key_dims = int(org_match) + int(region_match) + int(sector_match)

    # Label 3 — strong: all primary dims + TRL + semantically close
    if key_dims == 3 and trl_match and semantic_sim > 0.4:
        return 3

    # Label 2 — good: all primary dims (TRL or semantic may be off)
    if key_dims == 3:
        return 2

    # Label 1 — weak: two of three primary dims
    if key_dims == 2:
        return 1

    # Label 0 — irrelevant: two or more primary dims miss
    return 0


# ---------------------------------------------------------------------------
# Main training routine
# ---------------------------------------------------------------------------

def main() -> None:
    logger.info("Loading sentence embedder …")
    embedder = get_embedder()

    # Pre-encode all grant texts and all profile descriptions
    logger.info("Encoding %d grant texts …", len(GRANTS))
    grant_texts = [f"{g.title} {(g.description or '')[:500]}".strip() for g in GRANTS]
    grant_vecs = embedder.encode(grant_texts)  # (30, 384), L2-normalised

    logger.info("Encoding %d profile descriptions …", len(PROFILES))
    profile_texts = [p.description for p in PROFILES]
    profile_vecs = embedder.encode(profile_texts)  # (50, 384), L2-normalised

    # Pairwise cosine similarity matrix — shape (30, 50)
    sim_matrix = (grant_vecs @ profile_vecs.T).astype(float)

    # Build 1500 training rows (all 30 × 50 combinations)
    logger.info("Building 1500 feature rows …")
    X_rows: list[list[float]] = []
    y_labels: list[int] = []

    for gi, grant in enumerate(GRANTS):
        for pi, profile in enumerate(PROFILES):
            sem_sim = float(np.clip(sim_matrix[gi, pi], 0.0, 1.0))
            features = extract_features(grant, profile, sem_sim)
            X_rows.append([features[k] for k in FEATURE_NAMES])
            y_labels.append(_assign_label(grant, profile, sem_sim))

    X = np.array(X_rows, dtype=np.float32)
    y = np.array(y_labels, dtype=np.int32)

    # Label distribution report
    unique, counts = np.unique(y, return_counts=True)
    logger.info("Label distribution: %s", dict(zip(unique.tolist(), counts.tolist())))

    # ------------------------------------------------------------------ #
    # Train / test split (stratified)
    # ------------------------------------------------------------------ #
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )
    logger.info(
        "Train: %d rows | Test: %d rows", len(X_train), len(X_test)
    )

    # ------------------------------------------------------------------ #
    # XGBoost XGBClassifier
    # ------------------------------------------------------------------ #
    clf = XGBClassifier(
        objective="multi:softprob",
        num_class=4,
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="mlogloss",
        random_state=42,
        verbosity=0,
    )

    logger.info("Training XGBoost classifier …")
    clf.fit(
        X_train,
        y_train,
        eval_set=[(X_test, y_test)],
        verbose=False,
    )

    # ------------------------------------------------------------------ #
    # Evaluation
    # ------------------------------------------------------------------ #
    y_pred = clf.predict(X_test)

    acc = accuracy_score(y_test, y_pred)
    report = classification_report(
        y_test,
        y_pred,
        target_names=["irrelevant", "weak", "good", "strong"],
        zero_division=0,
    )

    print("\n" + "=" * 60)
    print("XGBoost reranker — evaluation on held-out 20%")
    print("=" * 60)
    print(f"Accuracy : {acc:.4f}")
    print()
    print(report)
    print("=" * 60 + "\n")

    # ------------------------------------------------------------------ #
    # Save model
    # ------------------------------------------------------------------ #
    MODEL_OUT.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(clf, str(MODEL_OUT))
    logger.info("Model saved to %s", MODEL_OUT)


if __name__ == "__main__":
    main()
