"""
Standalone checks for the keyword topic classifier.

Run with: python -m scripts.test_topic_classifier
"""

import sys

from app.topics import TOPIC_PATTERNS, classify_article_topic

UNCATEGORIZED = "Uncategorized"

# (text, expected topic)
CASES = [
    # Substrings that used to match and must not any more
    ("He said the plan was fine", UNCATEGORIZED),
    ("Protesters marched against the plan", UNCATEGORIZED),
    ("The app is now available on the web", UNCATEGORIZED),
    ("They built a shack by the lake", UNCATEGORIZED),
    ("Living with bipolar disorder", UNCATEGORIZED),
    ("Set the camera on a tripod", UNCATEGORIZED),
    ("The endgame of the trade war", UNCATEGORIZED),
    ("The pro gamer retired at 25", UNCATEGORIZED),
    ("The aftcraft model is a typo, not a regulator", UNCATEGORIZED),
    ("A paid email campaign", UNCATEGORIZED),
    # Whole words, phrases and plurals that must match
    ("AI is changing search", "Artificial Intelligence"),
    ("New ai agents ship today", "Artificial Intelligence"),
    ("OpenAI launches a new model", "Artificial Intelligence"),
    ("Advances in machine learning", "Artificial Intelligence"),
    ("Advances in machine\nlearning", "Artificial Intelligence"),
    ("AI-powered tools and the company's AI's limits", "Artificial Intelligence"),
    ("Open-source LLMs are catching up", "Artificial Intelligence"),
    ("A simple hack for faster builds", "Cybersecurity"),
    ("The company was hacked last week", "Cybersecurity"),
    ("Hackers stole customer data", "Cybersecurity"),
    ("Two data breaches disclosed", "Cybersecurity"),
    ("Show HN on Hacker News: my side project", UNCATEGORIZED),
    ("The FTC sues over the merger", "Policy & Regulation"),
    ("The FTC's new rule", "Policy & Regulation"),
    ("The company filed for an IPO", "Business & Finance"),
    ("A wave of pre-IPO deals", "Business & Finance"),
    ("SpaceX reaches orbit", "Space"),
    ("An orbital launch is planned", "Space"),
    ("Drones deliver packages", "Robotics"),
    ("New games coming to consoles", "Gaming & Entertainment"),
    # Consumer Tech
    ("Apple unveils the iPhone 18", "Consumer Tech"),
    ("The best laptops for students", "Consumer Tech"),
    ("Samsung's new foldable is thinner", "Consumer Tech"),
    ("AirPods Pro review: better noise cancelling", "Consumer Tech"),
    ("Meta's smart glasses get a display", "Consumer Tech"),
    ("Wearables that track your sleep", "Consumer Tech"),
    ("Google Pixel 11 leaks", "Consumer Tech"),
    ("Apple shares fell after earnings", UNCATEGORIZED),
    ("Watch the eclipse tonight", UNCATEGORIZED),
    ("The image is 4,000 pixels wide", UNCATEGORIZED),
    ("Pixelated graphics are back", UNCATEGORIZED),
    ("The deal was unfoldable from the start", UNCATEGORIZED),
    # Scoring rules are unchanged
    ("OpenAI and Anthropic face a lawsuit", "Artificial Intelligence"),
    ("An AI startup", UNCATEGORIZED),
    ("", UNCATEGORIZED),
]


def matched_keywords(text: str) -> list[str]:
    """Which topics' patterns hit, for printing alongside a failure."""
    lower = text.lower()
    return [
        f"{topic}:{pattern.pattern}"
        for topic, patterns in TOPIC_PATTERNS.items()
        for pattern in patterns
        if pattern.search(lower)
    ]


def main() -> int:
    failures = 0
    for text, expected in CASES:
        actual = classify_article_topic(text)
        ok = actual == expected
        failures += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {text!r:<52} -> {actual}")
        if not ok:
            print(f"      expected {expected}; matched {matched_keywords(text)}")

    print(f"\n{len(CASES) - failures}/{len(CASES)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
