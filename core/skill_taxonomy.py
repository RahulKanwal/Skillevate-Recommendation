"""
Skill taxonomy module — query expansion for the recommendation engine.

Strategy:
  1. Static map  — curated synonyms/related terms for known tech skills
  2. Dynamic fallback — GloVe word vectors loaded via numpy for skills
     not in the static map (no gensim required)

Usage:
    from core.skill_taxonomy import expand_skill
    terms = expand_skill("machine learning")
    # → ["machine learning", "deep learning", "neural networks", ...]
"""

import logging
import os
import numpy as np
from typing import List, Optional

logger = logging.getLogger(__name__)

# ── Static taxonomy ───────────────────────────────────────────────────────────

SKILL_TAXONOMY: dict[str, List[str]] = {
    # Python ecosystem
    "python": ["python programming", "python3", "pip", "virtualenv"],
    "django": ["django rest framework", "django orm", "python web"],
    "fastapi": ["fastapi python", "async python", "pydantic", "uvicorn"],
    "flask": ["flask python", "flask rest api", "python microframework"],

    # JavaScript / TypeScript ecosystem
    "javascript": ["js", "es6", "es2015", "vanilla javascript", "node.js"],
    "typescript": ["ts", "typed javascript", "typescript generics"],
    "nodejs": ["node.js", "node js", "npm", "express.js", "server-side javascript"],
    "react": ["reactjs", "react hooks", "jsx", "react components", "redux"],
    "vue": ["vuejs", "vue.js", "vue3", "nuxt"],
    "angular": ["angularjs", "angular cli", "rxjs", "typescript angular"],
    "nextjs": ["next.js", "react ssr", "vercel", "server side rendering"],

    # Machine learning / AI
    "machine learning": ["ml", "deep learning", "neural networks", "scikit-learn", "supervised learning"],
    "deep learning": ["neural networks", "cnn", "rnn", "transformer", "backpropagation"],
    "tensorflow": ["tf", "keras", "tensorflow2", "neural network tensorflow"],
    "pytorch": ["torch", "pytorch lightning", "autograd", "neural network pytorch"],
    "data science": ["data analysis", "pandas", "numpy", "matplotlib", "jupyter"],
    "nlp": ["natural language processing", "text classification", "transformers", "bert", "llm"],
    "computer vision": ["image recognition", "opencv", "cnn", "object detection", "yolo"],

    # DevOps / Cloud
    "docker": ["containerization", "dockerfile", "docker compose", "container"],
    "kubernetes": ["k8s", "container orchestration", "helm", "kubectl"],
    "devops": ["ci/cd", "continuous integration", "continuous deployment", "infrastructure as code"],
    "aws": ["amazon web services", "ec2", "s3", "lambda", "cloud computing"],
    "azure": ["microsoft azure", "azure devops", "azure functions", "cloud"],
    "gcp": ["google cloud", "google cloud platform", "bigquery", "cloud run"],
    "terraform": ["infrastructure as code", "iac", "cloud provisioning"],

    # Databases
    "sql": ["mysql", "postgresql", "database", "relational database", "queries"],
    "postgresql": ["postgres", "psql", "relational database"],
    "mongodb": ["nosql", "document database", "mongoose", "atlas"],
    "redis": ["caching", "in-memory database", "pub sub"],

    # Mobile
    "flutter": ["dart", "flutter widgets", "cross platform mobile"],
    "android": ["android development", "kotlin android", "java android", "android studio"],
    "ios": ["swift", "swiftui", "xcode", "objective-c", "apple development"],
    "react native": ["cross platform", "mobile javascript", "expo"],

    # Systems / Low-level
    "rust": ["rust lang", "ownership", "systems programming", "cargo"],
    "golang": ["go", "go lang", "goroutines", "concurrency go"],
    "c++": ["cpp", "c plus plus", "stl", "systems programming"],

    # Web fundamentals
    "html": ["html5", "semantic html", "web markup"],
    "css": ["css3", "flexbox", "grid", "responsive design", "sass", "tailwind"],
    "graphql": ["graphql api", "apollo", "schema", "queries mutations"],
    "rest api": ["restful", "http api", "api design", "openapi", "swagger"],

    # Security
    "cybersecurity": ["security", "ethical hacking", "penetration testing", "ctf"],
    "linux": ["bash", "shell scripting", "unix", "command line", "linux administration"],
}

# ── Career-path → skill boost terms ──────────────────────────────────────────

CAREER_EXPANSIONS: dict[str, List[str]] = {
    "backend":            ["api", "server", "database", "rest", "microservices"],
    "backend developer":  ["api", "server", "database", "rest", "microservices"],
    "frontend":           ["ui", "interface", "browser", "responsive", "css"],
    "frontend developer": ["ui", "interface", "browser", "responsive", "css"],
    "full stack":         ["api", "database", "ui", "deployment"],
    "data scientist":     ["analysis", "visualization", "statistics", "pandas", "jupyter"],
    "ml engineer":        ["model training", "deployment", "mlops", "pipeline"],
    "devops engineer":    ["ci/cd", "automation", "infrastructure", "monitoring"],
    "mobile developer":   ["mobile", "app", "ios", "android", "cross platform"],
}

# ── GloVe embedding fallback ──────────────────────────────────────────────────

_glove_vectors: Optional[dict] = None
_glove_load_attempted = False

# Path where the GloVe file is expected (user can place it here)
_GLOVE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "glove.6B.50d.txt")


def _load_glove() -> Optional[dict]:
    """
    Lazy-load GloVe 50d vectors from a local text file.
    Returns None if file not found — dynamic expansion is silently disabled.

    To enable: download glove.6B.zip from https://nlp.stanford.edu/projects/glove/
    and place glove.6B.50d.txt in the data/ directory.
    """
    global _glove_vectors, _glove_load_attempted
    if _glove_load_attempted:
        return _glove_vectors

    _glove_load_attempted = True
    glove_path = os.path.abspath(_GLOVE_PATH)

    if not os.path.exists(glove_path):
        logger.info(
            f"GloVe file not found at {glove_path}. "
            "Dynamic skill expansion disabled. "
            "Download glove.6B.50d.txt from https://nlp.stanford.edu/projects/glove/ "
            "and place it in the data/ directory to enable it."
        )
        return None

    try:
        logger.info("Loading GloVe vectors...")
        vectors = {}
        with open(glove_path, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.rstrip().split(" ")
                word = parts[0]
                vec = np.array(parts[1:], dtype=np.float32)
                vectors[word] = vec
        _glove_vectors = vectors
        logger.info(f"Loaded {len(vectors):,} GloVe vectors")
    except Exception as e:
        logger.warning(f"Failed to load GloVe vectors: {e}")
        _glove_vectors = None

    return _glove_vectors


def _dynamic_expand(skill: str, top_n: int = 3) -> List[str]:
    """
    Find semantically similar terms using GloVe cosine similarity.
    Falls back gracefully if vectors aren't available.
    """
    vectors = _load_glove()
    if vectors is None:
        return []

    try:
        token = skill.lower().split()[-1]
        if token not in vectors:
            return []

        query_vec = vectors[token]
        query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-9)

        # Compute cosine similarity against all vectors
        words = list(vectors.keys())
        matrix = np.stack([vectors[w] for w in words])
        norms = np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-9
        similarities = matrix / norms @ query_norm

        top_indices = np.argsort(similarities)[::-1][1: top_n * 3 + 1]
        stopwords = {"the", "a", "an", "is", "are", "was", "be", "to", "of", "and", "or"}
        results = [
            words[i] for i in top_indices
            if similarities[i] > 0.65
            and words[i] not in stopwords
            and len(words[i]) > 2
        ]
        return results[:top_n]
    except Exception as e:
        logger.debug(f"Dynamic expansion failed for '{skill}': {e}")
        return []


# ── Public API ────────────────────────────────────────────────────────────────

def expand_skill(skill: str, preferences: Optional[List[str]] = None) -> List[str]:
    """
    Return an expanded list of search terms for a given skill.
    """
    skill_lower = skill.lower().strip()
    terms = [skill_lower]

    # 1. Static taxonomy
    static_terms = SKILL_TAXONOMY.get(skill_lower, [])
    terms.extend(static_terms)

    # 2. Career-path expansion from preferences
    if preferences:
        for pref in preferences:
            pref_lower = pref.lower().strip()
            career_terms = CAREER_EXPANSIONS.get(pref_lower, [])
            terms.extend(career_terms)

    # 3. Dynamic GloVe fallback for unknown skills
    if not static_terms:
        terms.extend(_dynamic_expand(skill_lower))

    # Deduplicate preserving order
    seen: set = set()
    unique = []
    for t in terms:
        if t not in seen:
            seen.add(t)
            unique.append(t)

    return unique


def get_search_query_terms(skill: str, preferences: Optional[List[str]] = None) -> List[str]:
    """Return top search terms for provider queries (max 3)."""
    return expand_skill(skill, preferences)[:3]
