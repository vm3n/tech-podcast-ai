"""
Stage 2 — Groq Narrator
Generates natural podcast scripts using Groq.
First 6 articles per category get full deep dive.
Remaining articles get headline mention only.
"""

import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

SYSTEM_PROMPT = """
You are Herlin, a friendly and knowledgeable tech podcast host.
Your name is Herlin. You introduced yourself once at the very start of the show. Never introduce yourself again. Never say Hi I am Herlin or Hey there I am Herlin mid episode. Just tell each story directly and naturally as if continuing a conversation.
You explain things like you are talking to a smart friend over
coffee — not like you are writing a report.

Rules you must always follow:
- Write in spoken English only. No bullet points, no headers, no markdown.
- Use short sentences. Mix them with occasional longer ones for rhythm.
- Every technical term must be explained with a simple real world analogy.
- Never say "In conclusion", "Furthermore", "It is worth noting", or "Notably".
- Never use passive voice. Always say who did what.
- Use phrases like "here is the thing", "think of it this way",
  "and here is why that is a big deal", "so what does this mean for you".
- End every deep dive story with a practical takeaway for a software developer.
- Write exactly as you would say it out loud.
- Vary your sentence length for natural rhythm.
- IMPORTANT: Return ONLY the script text. No explanations of changes made.
  No bullet points of what you fixed. Just the clean spoken script.
"""

FULL_PROMPT = """
You have the full article below. Write a detailed podcast script
explaining this story deeply. Cover what happened, why it matters,
the background context, and what the listener should take away.

Article title: {title}

Full article:
{text}

Now write the podcast script. Start with a hook that makes
the listener lean in immediately. Return ONLY the script, nothing else.
"""

PARTIAL_PROMPT = """
You only have partial content for this story due to a paywall.
Use these words plus your own knowledge to explain what is happening
and why it matters. Tell the listener upfront you have limited info.

Article title: {title}

Partial content:
{text}

Write the podcast script. Return ONLY the script, nothing else.
"""

HEADLINE_PROMPT = """
Write a single short 2-3 sentence mention of this story for a podcast.
Just the headline — what happened and why it might matter.
No deep dive. Keep it under 50 words.
Return ONLY the 2-3 sentences, nothing else.

Story: {title}
"""


def generate_script(article, is_headline: bool = False) -> str:
    """
    Generates podcast script for one article.
    is_headline=True generates a short 2-3 sentence mention.
    is_headline=False generates a full deep dive script.
    """

    if is_headline:
        print(f"\n  Headline mention: {article.title[:60]}...")
        user_prompt = HEADLINE_PROMPT.format(
            title=article.title if not article.title.startswith("http")
            else article.url
        )
        temperature = 0.5
        max_tokens = 100
    else:
        print(f"\nDeep dive: {article.title[:60]}...")
        print(f"  Tier: {article.tier} ({article.word_count} words)")

        if article.tier == "full":
            user_prompt = FULL_PROMPT.format(
                title=article.title,
                text=article.text
            )
            temperature = 0.7
        elif article.tier == "partial":
            user_prompt = PARTIAL_PROMPT.format(
                title=article.title,
                text=article.text if article.text else "No text available."
            )
            temperature = 0.7
        else:
            user_prompt = HEADLINE_PROMPT.format(
                title=article.title if not article.title.startswith("http")
                else article.url
            )
            temperature = 0.5

        max_tokens = 1500

    # Truncate very long articles to avoid 413 error
    # Groq TPM limit is 12000 tokens per minute
    # 8000 words is roughly 10000 tokens which is safe
    if len(user_prompt.split()) > 8000:
        words = user_prompt.split()
        user_prompt = " ".join(words[:8000])
        print(f"  Truncated to 8000 words to avoid token limit")

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens
        )

        script = response.choices[0].message.content.strip()
        word_count = len(script.split())

        if is_headline:
            print(f"  Headline: {word_count} words")
        else:
            print(f"  Script: {word_count} words")

        return script

    except Exception as e:
        print(f"  Groq error: {e}")
        if is_headline:
            return f"Quick mention — {article.title[:100]}. Worth keeping an eye on."
        else:
            return f"We had trouble processing this story. Moving on."


def generate_episode_script(articles: list) -> str:
    """
    Generates full episode script.
    First 6 articles get deep dive treatment.
    Remaining articles get headline mentions.
    All stitched into one complete episode.
    """

    print("\n" + "="*50)
    print("GENERATING EPISODE SCRIPTS")
    print("="*50)

    deep_dive_articles = articles[:6]
    headline_articles = articles[6:]

    print(f"  Deep dives : {len(deep_dive_articles)}")
    print(f"  Headlines  : {len(headline_articles)}")

    scripts = []

    # Intro
    intro = (
        "Welcome to your daily tech briefing. "
        "I am Herlin, and today we have got some really interesting stories. "
        "Let us dive straight in."
    )
    scripts.append(intro)

    # Deep dive section
    print(f"\n--- DEEP DIVES ---")
    for i, article in enumerate(deep_dive_articles, 1):
        print(f"\nArticle {i} of {len(deep_dive_articles)}")
        script = generate_script(article, is_headline=False)

        if i < len(deep_dive_articles):
            script += "\n\nAlright, let us move on to the next story."

        scripts.append(script)

    # Headlines section
    if headline_articles:
        scripts.append(
            "\n\nNow let us quickly run through some other stories "
            "that caught our eye today."
        )

        print(f"\n--- HEADLINES ---")
        headline_scripts = []
        for article in headline_articles:
            hl = generate_script(article, is_headline=True)
            headline_scripts.append(hl)

        scripts.append(" ".join(headline_scripts))

    # Outro
    outro = (
        "\n\nAnd that is your tech briefing for today. "
        "A lot happening as always. "
        "Stay curious, keep building, and I will see you tomorrow."
    )
    scripts.append(outro)

    full_episode = "\n\n".join(scripts)

    total_words = len(full_episode.split())
    print(f"\n{'='*50}")
    print(f"EPISODE COMPLETE")
    print(f"  Total words : {total_words}")
    print(f"  Deep dives  : {len(deep_dive_articles)}")
    print(f"  Headlines   : {len(headline_articles)}")
    print(f"  Est. runtime: ~{total_words // 130} minutes")
    print(f"{'='*50}")

    return full_episode


if __name__ == "__main__":
    from fetcher import fetch_multiple

    test_urls = [
        "https://arstechnica.com",
        "https://techcrunch.com",
    ]

    print("Testing narrator...")
    from fetcher import fetch_multiple
    articles = fetch_multiple(test_urls)
    script = generate_episode_script(articles)
    print("\nPreview:")
    print(script[:500])
