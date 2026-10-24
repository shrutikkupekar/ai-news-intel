"""
Keyword-based topic classification.

Kept separate from the entity processor so it can be imported (and tested)
without loading spaCy or the embedding model.
"""

import re

TOPIC_TAXONOMY = {
    "Artificial Intelligence": [
        "ai",
        "chatgpt",
        "llm",
        "machine learning",
        "openai",
        "anthropic",
        "claude",
    ],
    "Robotics": [
        "robot",
        "robotics",
        "automation",
        "drone",
        "humanoid",
    ],
    "Space": [
        "nasa",
        "spacex",
        "satellite",
        "rocket",
        "orbit",
        "astronaut",
    ],
    "Business & Finance": [
        "funding",
        "valuation",
        "ipo",
        "acquisition",
        "investor",
        "startup",
    ],
    "Policy & Regulation": [
        "regulation",
        "lawsuit",
        "congress",
        "senate",
        "ftc",
        "antitrust",
    ],
    "Gaming & Entertainment": [
        "game",
        "gaming",
        "movie",
        "streaming",
        "netflix",
    ],
    "Cybersecurity": [
        "hack",
        "breach",
        "vulnerability",
        "malware",
        "exploit",
    ],
}

# Every keyword also matches its plural ("drones", "breaches"). These add the
# other word forms that clearly mean the same thing for topic purposes.
EXTRA_FORMS = {
    "hack": ["hacked", "hacker", "hackers", "hacking"],
    "breach": ["breached"],
    "exploit": ["exploited", "exploiting"],
    "orbit": ["orbital", "orbiting"],
    "robot": ["robotic"],
}

# "Hacker News" is a site name, not a security story
NEGATIVE_LOOKAHEADS = {
    "hack": r"(?!\s+news\b)",
}


def _keyword_pattern(keyword: str) -> re.Pattern:
    """
    Whole-word pattern for a keyword or phrase, with an optional plural.

    \\b on both sides stops "ai" matching inside "said" or "openai", and
    "ipo" inside "recipe". Phrases match across any run of whitespace.
    """
    body = r"\s+".join(re.escape(word) for word in keyword.split())
    forms = [body + r"(?:s|es)?"] + [re.escape(form) for form in EXTRA_FORMS.get(keyword, [])]
    lookahead = NEGATIVE_LOOKAHEADS.get(keyword, "")
    return re.compile(r"\b(?:" + "|".join(forms) + r")\b" + lookahead)


TOPIC_PATTERNS = {
    topic: [_keyword_pattern(keyword) for keyword in keywords]
    for topic, keywords in TOPIC_TAXONOMY.items()
}


def classify_article_topic(text: str) -> str:
    """
    Classify article text into a topic based on keyword matching.

    Each keyword counts once if it appears anywhere as a whole word. Returns
    the topic with the most matching keywords, or "Uncategorized" if there's
    a tie or zero matches.
    """
    text_lower = text.lower()
    topic_scores = {
        topic: sum(1 for pattern in patterns if pattern.search(text_lower))
        for topic, patterns in TOPIC_PATTERNS.items()
    }

    max_score = max(topic_scores.values())
    if max_score == 0:
        return "Uncategorized"

    topics_with_max = [t for t, s in topic_scores.items() if s == max_score]

    if len(topics_with_max) > 1:
        # Tie: return "Uncategorized"
        return "Uncategorized"

    return topics_with_max[0]
