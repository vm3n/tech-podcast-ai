"""
Dedup — Three layer duplicate detection
Layer 1: Exact URL match (handled in database.py)
Layer 2: Title word similarity (handled in database.py)
Layer 3: Groq semantic understanding (this file)
"""

import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def semantic_dedup(articles: list) -> list:
    """
    Uses Groq to find articles covering the same story.
    Returns only unique articles.
    """

    if len(articles) <= 1:
        return articles

    print("\n  Running semantic dedup with Groq...")

    # Build list of titles and urls for Groq
    article_list = []
    for i, article in enumerate(articles):
        title = article.title
        # Use first 100 words of text as context
        preview = " ".join(article.text.split()[:100]) if article.text else ""
        article_list.append({
            "index": i,
            "title": title,
            "preview": preview
        })

    prompt = f"""
You are a news deduplication system.

Here is a list of articles. Your job is to find which ones
cover the SAME story or topic — even if the titles and URLs
are different.

Articles:
{json.dumps(article_list, indent=2)}

Rules:
- Articles about the same news event are duplicates
- Articles about the same product launch are duplicates
- Articles about different aspects of a broad topic are NOT duplicates
- Keep the article with the most content (highest index usually has more detail)

Return ONLY a JSON array of indexes to KEEP.
Example: [0, 2, 4]
No explanation. Just the JSON array.
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=200
        )

        result = response.choices[0].message.content.strip()

        # Parse the JSON array
        # Remove any markdown code blocks if present
        result = result.replace("```json", "").replace("```", "").strip()
        indexes_to_keep = json.loads(result)

        # Filter articles
        unique_articles = [
            articles[i] for i in indexes_to_keep
            if i < len(articles)
        ]

        removed = len(articles) - len(unique_articles)
        if removed > 0:
            print(f"  Groq removed {removed} duplicate stories")
        else:
            print(f"  No duplicates found by Groq")

        return unique_articles

    except Exception as e:
        print(f"  Semantic dedup error: {e}")
        print(f"  Falling back to all articles")
        return articles


def full_dedup(articles: list, episode_date: str) -> list:
    """
    Runs all three dedup layers in order.
    Returns clean list of unique articles.
    """
    from database import is_url_seen, is_title_seen

    print("\n" + "="*50)
    print("DEDUP CHECK")
    print("="*50)
    print(f"  Input articles: {len(articles)}")

    # Layer 1 — URL dedup (already processed URLs)
    layer1 = []
    for article in articles:
        if is_url_seen(article.url, days=7):
            print(f"  [URL dup] Skipping: {article.url[:60]}")
        else:
            layer1.append(article)
    print(f"  After URL dedup: {len(layer1)}")

    # Layer 2 — Title similarity dedup
    layer2 = []
    for article in articles:
        if is_title_seen(article.title, days=7):
            print(f"  [Title dup] Skipping: {article.title[:60]}")
        else:
            layer2.append(article)
    print(f"  After title dedup: {len(layer2)}")

    # Layer 3 — Groq semantic dedup
    layer3 = semantic_dedup(layer2)
    print(f"  After semantic dedup: {len(layer3)}")

    print(f"\n  Final unique articles: {len(layer3)}")
    print("="*50)

    return layer3


if __name__ == "__main__":
    # Test semantic dedup with fake articles
    from dataclasses import dataclass

    @dataclass
    class MockArticle:
        url: str
        title: str
        text: str
        word_count: int
        tier: str

    test_articles = [
        MockArticle(
            url="https://techcrunch.com/openai-gpt5",
            title="OpenAI launches GPT-5 with major improvements",
            text="OpenAI today announced GPT-5 their latest model...",
            word_count=500,
            tier="full"
        ),
        MockArticle(
            url="https://theverge.com/openai-gpt5",
            title="GPT-5 is finally here and it is impressive",
            text="OpenAI released GPT-5 today marking a new era...",
            word_count=400,
            tier="full"
        ),
        MockArticle(
            url="https://arstechnica.com/apple-m4",
            title="Apple announces M4 chip with neural engine",
            text="Apple today unveiled the M4 chip for MacBooks...",
            word_count=600,
            tier="full"
        ),
    ]

    print("Testing semantic dedup...")
    print("Articles 1 and 2 are about the same story (GPT-5)")
    print("Article 3 is different (Apple M4)")
    print("Expected result: 2 articles kept\n")

    result = semantic_dedup(test_articles)
    print(f"\nKept {len(result)} articles:")
    for a in result:
        print(f"  - {a.title}")
