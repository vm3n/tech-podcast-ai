"""
Stage 2 — Groq Narrator
Takes fetched article text and generates a natural
podcast script using Groq's llama-3.3-70b model.
Includes quality check pass to catch robotic sentences.
"""

import os
from groq import Groq
from dotenv import load_dotenv
from fetcher import FetchedArticle

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

SYSTEM_PROMPT = """
You are Herlin, a friendly and knowledgeable tech podcast host.
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
- End every story with a practical takeaway for a software developer.
- Write exactly as you would say it out loud.
- Vary your sentence length. Short punchy ones after a long explanation
  create natural rhythm.
- Target length: 700 to 1000 words. This equals roughly 5 to 7 minutes of audio.
"""

FULL_PROMPT = """
You have the full article below. Write a detailed podcast script
explaining this story deeply. Cover what happened, why it matters,
the background context, and what the listener should take away.

Article title: {title}

Full article:
{text}

Now write the podcast script. Start with a hook that makes
the listener lean in immediately.
"""

PARTIAL_PROMPT = """
You only have partial content for this story — likely because
of a paywall. Use these words plus your own knowledge of this
topic to explain what is happening and why it matters.

Important: Tell the listener upfront that you only have limited
information on this one, but still give them as much useful
context as you can from what you know about this topic.

Article title: {title}

Partial content:
{text}

Now write the podcast script.
"""

HEADLINE_PROMPT = """
You only have the headline for this story — no article text
was available. Give a 30 second mention of this story.
Tell the listener this one is worth watching and why,
based on your knowledge of the topic.

Headline: {title}

Write a short 30 second mention only.
"""


def quality_check(script: str) -> str:
    """
    Second Groq pass — reads the generated script
    and fixes any sentences that sound robotic,
    too formal, or written rather than spoken.
    """

    print("  Running quality check...")

    checker_prompt = f"""
Read this podcast script carefully.

Find any sentences that:
- Sound too formal or written rather than spoken
- Use passive voice (e.g. "was announced by" instead of "announced")
- Use jargon without explaining it
- Are longer than 35 words
- Use phrases like "In conclusion", "Furthermore",
  "It is worth noting", "Notably", "It is important to"

For each problem sentence, rewrite it in a natural spoken way.

Return the FULL script with fixes applied.
If nothing needs fixing, return the script exactly as is.

Script:
{script}
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "user", "content": checker_prompt}
            ],
            temperature=0.3,
            max_tokens=2000
        )

        improved = response.choices[0].message.content.strip()
        print("  Quality check complete")
        return improved

    except Exception as e:
        print(f"  Quality check error: {e} — using original")
        return script


def generate_script(article: FetchedArticle) -> str:
    """
    Generates a natural spoken podcast script from a fetched article.
    Uses different prompts based on confidence tier.
    Runs quality check pass before returning.
    """

    print(f"\nGenerating script for: {article.title[:60]}...")
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

    else:  # headline
        user_prompt = HEADLINE_PROMPT.format(
            title=article.title
        )
        temperature = 0.6

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature,
            max_tokens=1500
        )

        script = response.choices[0].message.content.strip()

        # Run quality check pass
        script = quality_check(script)

        word_count = len(script.split())
        print(f"  Final script: {word_count} words")
        return script

    except Exception as e:
        print(f"  Groq error: {e}")
        return f"We had trouble processing this story about {article.title}. Moving on."


def generate_episode_script(articles: list) -> str:
    """
    Generates scripts for all articles and stitches them
    into one full episode script with intro and outro.
    """

    print("\n" + "="*50)
    print("GENERATING EPISODE SCRIPTS")
    print("="*50)

    scripts = []

    # Intro
    intro = (
        "Welcome to your daily tech briefing. "
        "I am Herlin, and today we have got some really interesting stories. "
        "Let us dive straight in."
    )
    scripts.append(intro)

    # Generate script for each article
    for i, article in enumerate(articles, 1):
        print(f"\nArticle {i} of {len(articles)}")
        script = generate_script(article)

        # Add a natural transition between stories
        if i < len(articles):
            script += "\n\nAlright, let us move on to the next story."

        scripts.append(script)

    # Outro
    outro = (
        "And that is your tech briefing for today. "
        "A lot happening as always. "
        "Stay curious, keep building, and I will see you tomorrow."
    )
    scripts.append(outro)

    full_episode = "\n\n".join(scripts)

    total_words = len(full_episode.split())
    print(f"\n{'='*50}")
    print(f"EPISODE COMPLETE")
    print(f"  Total words : {total_words}")
    print(f"  Est. runtime: ~{total_words // 130} minutes")
    print(f"{'='*50}")

    return full_episode


if __name__ == "__main__":
    from fetcher import fetch_multiple

    test_urls = [
        "https://arstechnica.com",
    ]

    print("Testing Groq narrator with quality check...")
    print("="*50)

    articles = fetch_multiple(test_urls)
    episode_script = generate_episode_script(articles)

    print("\nSCRIPT PREVIEW (first 500 chars):")
    print("-"*50)
    print(episode_script[:500])
    print("-"*50)

    with open("scripts/test_episode.txt", "w") as f:
        f.write(episode_script)

    print("\nFull script saved to scripts/test_episode.txt")
