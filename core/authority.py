"""
Authority scoring module.

Maintains whitelists of trusted YouTube channels and GitHub orgs.
Provides a score boost to content from official/authoritative sources.

To add new sources, update AUTHORITY_SOURCES.md and the dicts below.
"""

from typing import Optional

# ── YouTube Channel Whitelists ────────────────────────────────────────────────

# Trusted educational platforms — boost applies regardless of skill
TRUSTED_YOUTUBE_CHANNELS = {
    "UC8butISFwT-Wl7EV0hUK0BQ",  # freeCodeCamp.org
    "UC29ju8bIPH5as8OGnQzwJyA",  # Traversy Media
    "UCnUYZLuoy1rq1aVMwx4aTzw",  # Google for Developers
    "UCKWaEZ-_VweaEx1j62do_vQ",  # IBM Technology
    "UCEBb1b_L6zDS3xTUrIALZOw",  # MIT OpenCourseWare
    "UCxX9wt5FWQUAAz4UrysqK9A",  # CS Dojo
    "UCCTVrRJOwzEHm1ynH2c74IA",  # Corey Schafer
}

# Official channels for specific skills — highest authority tier
# Key: skill keyword (lowercase), Value: set of channel IDs
OFFICIAL_YOUTUBE_CHANNELS: dict[str, set[str]] = {
    "python":       {"UCWr0mx597DnSGLFk1WfvSkQ"},           # Python Software Foundation
    "docker":       {"UCZgt6AzoyjslHTC9dz0UoTw"},           # Docker official
    "kubernetes":   {"UCdngmbVKX1Tgre699-XLlUA"},           # TechWorld with Nana
    "devops":       {"UCdngmbVKX1Tgre699-XLlUA"},           # TechWorld with Nana
    "tensorflow":   {"UCWN3xxRkmTPmbKwht9FuE5A"},           # TensorFlow
    "pytorch":      {"UCWN3xxRkmTPmbKwht9FuE5A"},           # PyTorch
    "machine learning": {"UCWN3xxRkmTPmbKwht9FuE5A"},       # TensorFlow/PyTorch
    "data science": {"UCSNeZleDn9c74yQc-EKnVTA"},           # Kaggle
    "aws":          {"UCd6MoB9NC6uYN2grvUNT-Zg"},           # Amazon Web Services
    "android":      {"UCVHyOkuRLpR9An0-9IQZFHQ"},           # Android Developers
    "flutter":      {"UCwXdFgeE9KYzlDdR7TG9cMw"},           # Flutter official
}

# Trusted channel names (fallback when channel ID isn't in snippet)
TRUSTED_YOUTUBE_CHANNEL_NAMES = {
    "freecodecamp", "traversy media", "google for developers",
    "ibm technology", "mit opencourseware", "techworld with nana",
    "corey schafer", "cs dojo", "tensorflow", "pytorch", "kaggle",
    "android developers", "flutter", "docker", "fireship",
}

# ── GitHub Org Whitelists ─────────────────────────────────────────────────────

# Trusted orgs — boost applies regardless of skill
TRUSTED_GITHUB_ORGS = {
    "google", "microsoft", "ibm", "meta", "aws", "awslabs",
    "apache", "cncf", "freecodecamp",
}

# Official orgs for specific skills
# Key: skill keyword (lowercase), Value: set of org logins (lowercase)
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
    "official":           1.0,   # Official org/channel for this exact skill
    "trusted_platform":   0.8,   # Universally trusted educational source
    "known_educational":  0.5,   # Known platform, not skill-specific official
    "unknown":            0.0,   # No authority signal
}


# ── Public API ────────────────────────────────────────────────────────────────

def get_youtube_authority(channel_id: Optional[str], channel_name: Optional[str], skill: str) -> float:
    """
    Return authority score for a YouTube video based on its channel.

    Checks in order:
    1. Is the channel ID in the official list for this skill? → 1.0
    2. Is the channel ID in the generic trusted list? → 0.8
    3. Does the channel name match a trusted name? → 0.8
    4. Otherwise → 0.0
    """
    skill_lower = skill.lower()

    # Check official skill-specific channels
    for skill_keyword, channel_ids in OFFICIAL_YOUTUBE_CHANNELS.items():
        if skill_keyword in skill_lower and channel_id in channel_ids:
            return AUTHORITY_SCORES["official"]

    # Check generic trusted channels by ID
    if channel_id and channel_id in TRUSTED_YOUTUBE_CHANNELS:
        return AUTHORITY_SCORES["trusted_platform"]

    # Fallback: check channel name
    if channel_name:
        name_lower = channel_name.lower()
        if any(trusted in name_lower for trusted in TRUSTED_YOUTUBE_CHANNEL_NAMES):
            return AUTHORITY_SCORES["trusted_platform"]

    return AUTHORITY_SCORES["unknown"]


def get_github_authority(org_login: Optional[str], skill: str) -> float:
    """
    Return authority score for a GitHub repo based on its owner org.

    Checks in order:
    1. Is the org in the official list for this skill? → 1.0
    2. Is the org in the generic trusted list? → 0.8
    3. Otherwise → 0.0
    """
    if not org_login:
        return AUTHORITY_SCORES["unknown"]

    org_lower = org_login.lower()
    skill_lower = skill.lower()

    # Check official skill-specific orgs
    for skill_keyword, orgs in OFFICIAL_GITHUB_ORGS.items():
        if skill_keyword in skill_lower and org_lower in orgs:
            return AUTHORITY_SCORES["official"]

    # Check generic trusted orgs
    if org_lower in TRUSTED_GITHUB_ORGS:
        return AUTHORITY_SCORES["trusted_platform"]

    return AUTHORITY_SCORES["unknown"]
