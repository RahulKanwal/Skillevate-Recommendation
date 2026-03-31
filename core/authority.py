"""
Authority scoring module.

Maintains whitelists of trusted YouTube channels and GitHub orgs.
Provides a score boost to content from official/authoritative sources.

Tiers (highest → lowest):
  official      1.0  — official org/channel for this exact skill
  institute     0.95 — university / research institution (MIT, Stanford, etc.)
  trusted       0.8  — universally trusted educational platform
  unknown       0.0  — no authority signal

To add new sources, update AUTHORITY_SOURCES.md and the dicts below.
"""

from typing import Optional

# ── Academic Institutions ─────────────────────────────────────────────────────

# YouTube channel IDs for universities and research institutions
INSTITUTE_YOUTUBE_CHANNELS = {
    "UCEBb1b_L6zDS3xTUrIALZOw",  # MIT OpenCourseWare
    "UCoxcjq-8xIDTYp3uz647V5A",  # Numberphile (math)
    "UCYO_jab_esuFRV4b17AJtAg",  # 3Blue1Brown
    "UCnUYZLuoy1rq1aVMwx4aTzw",  # Google for Developers
    "UCVHFbw7woebKtfvug_tMXDQ",  # Stanford Online
    "UCBcRF18a7Qf58cCRy5xuWwQ",  # Harvard Online
    "UC_x5XG1OV2P6uZZ5FSM9Ttw",  # Google Developers (Android)
    "UCnUYZLuoy1rq1aVMwx4aTzw",  # Google Developers
    "UCJXGnMHhqU9lMkesHRmqFGQ",  # IIT Bombay (NPTEL)
    "UC3PkKoi-n6TL4_8S2oVAHhA",  # NPTEL-NOC IITM
    "UCHhiy3h3QkIfGWZngTwl_5w",  # Carnegie Mellon University
    "UCq0EGvLTyy-LLT1oUSO_0FQ",  # edX
    "UCkUq-s6z57uJFUFBvZIVTyg",  # Coursera
}

# Institute channel name fragments for fallback matching
INSTITUTE_YOUTUBE_CHANNEL_NAMES = {
    "mit opencourseware", "stanford", "harvard", "berkeley",
    "carnegie mellon", "cmu", "nptel", "iit", "caltech",
    "oxford", "cambridge", "yale", "princeton", "columbia",
    "georgia tech", "university", "coursera", "edx", "udacity",
    "3blue1brown", "google developers", "google for developers",
}

# GitHub orgs for universities and research institutions
INSTITUTE_GITHUB_ORGS = {
    "mit", "mit-pdos", "mitocw",
    "stanford-cs", "stanfordnlp", "stanford-oval",
    "harvard", "harvardnlp",
    "cmu-db", "cmu-perceptual-computing-lab",
    "berkeley-ai-research", "bair-climate-initiative",
    "google-research", "google-deepmind", "deepmind",
    "openai", "facebookresearch", "microsoft-research",
    "huggingface",
}

# ── YouTube Channel Whitelists ────────────────────────────────────────────────

TRUSTED_YOUTUBE_CHANNELS = {
    "UC8butISFwT-Wl7EV0hUK0BQ",  # freeCodeCamp.org
    "UC29ju8bIPH5as8OGnQzwJyA",  # Traversy Media
    "UCKWaEZ-_VweaEx1j62do_vQ",  # IBM Technology
    "UCxX9wt5FWQUAAz4UrysqK9A",  # CS Dojo
    "UCCTVrRJOwzEHm1ynH2c74IA",  # Corey Schafer
}

OFFICIAL_YOUTUBE_CHANNELS: dict[str, set[str]] = {
    "python":           {"UCWr0mx597DnSGLFk1WfvSkQ"},           # Python Software Foundation
    "docker":           {"UCZgt6AzoyjslHTC9dz0UoTw"},           # Docker official
    "kubernetes":       {"UCdngmbVKX1Tgre699-XLlUA"},           # TechWorld with Nana
    "devops":           {"UCdngmbVKX1Tgre699-XLlUA"},           # TechWorld with Nana
    "tensorflow":       {"UCWN3xxRkmTPmbKwht9FuE5A"},           # TensorFlow
    "pytorch":          {"UCWN3xxRkmTPmbKwht9FuE5A"},           # PyTorch
    "machine learning": {"UCWN3xxRkmTPmbKwht9FuE5A"},           # TensorFlow/PyTorch
    "data science":     {"UCSNeZleDn9c74yQc-EKnVTA"},           # Kaggle
    "aws":              {"UCd6MoB9NC6uYN2grvUNT-Zg"},           # Amazon Web Services
    "android":          {"UCVHyOkuRLpR9An0-9IQZFHQ"},           # Android Developers
    "flutter":          {"UCwXdFgeE9KYzlDdR7TG9cMw"},           # Flutter official
}

TRUSTED_YOUTUBE_CHANNEL_NAMES = {
    "freecodecamp", "traversy media", "ibm technology",
    "corey schafer", "cs dojo", "tensorflow", "pytorch", "kaggle",
    "android developers", "flutter", "docker", "fireship",
}

# ── GitHub Org Whitelists ─────────────────────────────────────────────────────

TRUSTED_GITHUB_ORGS = {
    "google", "microsoft", "ibm", "meta", "aws", "awslabs",
    "apache", "cncf", "freecodecamp",
}

OFFICIAL_GITHUB_ORGS: dict[str, set[str]] = {
    "python":           {"python", "psf"},
    "javascript":       {"tc39"},
    "typescript":       {"microsoft", "tc39"},
    "react":            {"facebook", "reactjs"},
    "vue":              {"vuejs"},
    "angular":          {"angular"},
    "docker":           {"docker", "moby"},
    "kubernetes":       {"kubernetes"},
    "tensorflow":       {"tensorflow"},
    "pytorch":          {"pytorch"},
    "machine learning": {"tensorflow", "pytorch", "scikit-learn"},
    "rust":             {"rust-lang"},
    "golang":           {"golang"},
    "go":               {"golang"},
    "swift":            {"apple"},
    "kotlin":           {"jetbrains"},
    "android":          {"android", "jetbrains"},
    "flutter":          {"flutter", "dart-lang"},
    "dart":             {"dart-lang"},
    "aws":              {"aws", "awslabs"},
    "azure":            {"azure", "microsoft"},
    "nodejs":           {"nodejs"},
    "django":           {"django"},
    "fastapi":          {"tiangolo"},
    "nextjs":           {"vercel"},
    "linux":            {"torvalds"},
}

# ── Scoring Tiers ─────────────────────────────────────────────────────────────

AUTHORITY_SCORES = {
    "official":     1.0,   # Official org/channel for this exact skill
    "institute":    0.95,  # University / research institution
    "trusted":      0.8,   # Universally trusted educational platform
    "unknown":      0.0,   # No authority signal
}


# ── Public API ────────────────────────────────────────────────────────────────

def get_youtube_authority(channel_id: Optional[str], channel_name: Optional[str], skill: str) -> float:
    """
    Return authority score for a YouTube video based on its channel.

    Checks in order:
    1. Official skill-specific channel  → 1.0
    2. Academic institution channel     → 0.95
    3. Generic trusted platform         → 0.8
    4. Otherwise                        → 0.0
    """
    skill_lower = skill.lower()

    # 1. Official skill-specific channels
    for skill_keyword, channel_ids in OFFICIAL_YOUTUBE_CHANNELS.items():
        if skill_keyword in skill_lower and channel_id in channel_ids:
            return AUTHORITY_SCORES["official"]

    # 2. Institute channels — by ID
    if channel_id and channel_id in INSTITUTE_YOUTUBE_CHANNELS:
        return AUTHORITY_SCORES["institute"]

    # 2b. Institute channels — by name fragment
    if channel_name:
        name_lower = channel_name.lower()
        if any(inst in name_lower for inst in INSTITUTE_YOUTUBE_CHANNEL_NAMES):
            return AUTHORITY_SCORES["institute"]

    # 3. Generic trusted channels — by ID
    if channel_id and channel_id in TRUSTED_YOUTUBE_CHANNELS:
        return AUTHORITY_SCORES["trusted"]

    # 3b. Generic trusted channels — by name
    if channel_name:
        name_lower = channel_name.lower()
        if any(trusted in name_lower for trusted in TRUSTED_YOUTUBE_CHANNEL_NAMES):
            return AUTHORITY_SCORES["trusted"]

    return AUTHORITY_SCORES["unknown"]


def get_github_authority(org_login: Optional[str], skill: str) -> float:
    """
    Return authority score for a GitHub repo based on its owner org.

    Checks in order:
    1. Official skill-specific org      → 1.0
    2. Academic / research institution  → 0.95
    3. Generic trusted org              → 0.8
    4. Otherwise                        → 0.0
    """
    if not org_login:
        return AUTHORITY_SCORES["unknown"]

    org_lower = org_login.lower()
    skill_lower = skill.lower()

    # 1. Official skill-specific orgs
    for skill_keyword, orgs in OFFICIAL_GITHUB_ORGS.items():
        if skill_keyword in skill_lower and org_lower in orgs:
            return AUTHORITY_SCORES["official"]

    # 2. Institute orgs
    if org_lower in INSTITUTE_GITHUB_ORGS:
        return AUTHORITY_SCORES["institute"]

    # 3. Generic trusted orgs
    if org_lower in TRUSTED_GITHUB_ORGS:
        return AUTHORITY_SCORES["trusted"]

    return AUTHORITY_SCORES["unknown"]
