cat > README.md << 'ENDOFFILE'
# Tech Podcast AI 🎙️

A fully automated personal podcast pipeline that reads your tech newsletters every morning and delivers deep dive audio episodes directly to your podcast app — completely free, completely private, zero manual effort after setup.

---

## What it does

Every morning when you open your Mac:

1. Reads your TLDR newsletters from Gmail automatically
2. Decodes all article links from tracking URLs
3. Fetches full article content from each link
4. Uses Groq AI to write natural spoken podcast scripts
5. Converts scripts to audio using Kokoro TTS locally on your Mac
6. Pushes MP3 episodes to GitHub Pages
7. Your podcast app picks them up automatically

You just open Apple Podcasts and hit play.

---

## Categories covered

| Category | What it covers |
|---|---|
| AI | Artificial intelligence, LLMs, model releases, AI research |
| Dev | Software development, coding tools, frameworks, best practices |
| Tech | Broad tech news, startups, big picture industry stories |
| Data | Data engineering, machine learning, analytics, databases |
| IT | Infrastructure, cloud, enterprise tech, DevOps |

---

## Episode format

Each daily episode per category contains:
- **5 deep dive stories** — fully explained in natural spoken language, 5-7 minutes each
- **Headline mentions** — remaining stories covered in 2-3 sentences each
- **Total runtime** — approximately 30-40 minutes per category

---

## Tech stack

| Component | Technology | Cost |
|---|---|---|
| Newsletter source | TLDR newsletters via Gmail API | Free |
| Article fetching | trafilatura + requests | Free |
| URL decoding | Custom TLDR tracker decoder | Free |
| Duplicate detection | 3-layer dedup system | Free |
| AI narration | Groq llama-3.3-70b-versatile | Free |
| Text to speech | Kokoro TTS (runs locally) | Free |
| Audio encoding | ffmpeg + pydub | Free |
| Episode storage | GitHub Pages | Free |
| Podcast feed | RSS 2.0 via feedgen | Free |
| Database | SQLite | Free |
| Automation | macOS launchd + login agent | Free |

**Total monthly cost: $0**

---

## How the pipeline works
Gmail (label:Podcasts)
↓
Decode TLDR tracking URLs → real article URLs
↓
Filter ads, sponsors, junk links
↓
Fetch full article text (trafilatura)
↓
3-layer dedup check
Layer 1: exact URL match (7 day window)
Layer 2: title word similarity
Layer 3: Groq semantic understanding
↓
Groq generates spoken podcast script
First 5 articles → full deep dive (5-7 min each)
Remaining articles → headline mention (2-3 sentences)
↓
Kokoro TTS converts script to MP3
↓
Git push to GitHub Pages
↓
RSS feed updated
↓
Podcast app downloads episode automatically

---

## Project structure
tech-podcast-ai/
├── main.py              # Main pipeline orchestrator
├── gmail_fetcher.py     # Gmail ingestion + TLDR URL decoding
├── fetcher.py           # Article content fetcher with title extraction
├── narrator.py          # Groq AI script generation
├── tts.py               # Kokoro TTS audio generation
├── dedup.py             # 3-layer duplicate story detection
├── database.py          # SQLite URL and episode tracking
├── run_if_needed.py     # Login trigger — runs pipeline if no episodes yet
├── requirements.txt     # Python dependencies
├── episodes/            # Generated MP3 files (auto cleaned after 3 days)
│   └── YYYY-MM-DD/
│       ├── ai.mp3
│       ├── dev.mp3
│       ├── tech.mp3
│       ├── data.mp3
│       └── it.mp3
├── scripts/             # Generated podcast scripts for reference
│   └── YYYY-MM-DD/
│       ├── ai.txt
│       └── ...
└── feed_*.xml           # RSS feeds per category (hosted on GitHub Pages)

---

## RSS feed URLs

Subscribe to these in any podcast app (Apple Podcasts, Pocket Casts, Overcast):
https://vm3n.github.io/tech-podcast-ai/feed_ai.xml
https://vm3n.github.io/tech-podcast-ai/feed_dev.xml
https://vm3n.github.io/tech-podcast-ai/feed_tech.xml
https://vm3n.github.io/tech-podcast-ai/feed_data.xml
https://vm3n.github.io/tech-podcast-ai/feed_it.xml

To add in Apple Podcasts:
- Mac: File → Follow a Show → paste URL
- iPhone: Search → paste URL in search bar

---

## Setup guide

### 1. Clone and install

```bash
git clone https://github.com/vm3n/tech-podcast-ai.git
cd tech-podcast-ai
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
brew install ffmpeg
```

### 2. Set up Gmail API

1. Go to console.cloud.google.com
2. Create a new project called tech-podcast
3. Enable the Gmail API
4. Create OAuth credentials (Desktop app)
5. Download as credentials.json and place in project folder
6. Create a Gmail label called Podcasts
7. Set up filters to tag your TLDR newsletters with this label

### 3. Set up Groq API

1. Go to console.groq.com
2. Sign up for free
3. Create an API key
4. Create a .env file:
GROQ_API_KEY=your_groq_api_key_here

### 4. Run manually

```bash
source venv/bin/activate
python3 main.py
```

First run will open a browser for Gmail OAuth login.

### 5. Set up automation (macOS)

Wake Mac at 6:55am daily:
```bash
sudo pmset repeat wakeorpoweron MTWRFSU 06:55:00
```

Create launchd agent to run pipeline at login:
```bash
# Copy com.techpodcast.login.plist to ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.techpodcast.login.plist
```

---

## How dedup works

The pipeline uses three layers to make sure you never hear the same story twice:

**Layer 1 — URL dedup**
Every processed URL is stored in SQLite with a timestamp. Any URL seen in the last 7 days is skipped automatically.

**Layer 2 — Title similarity**
Article titles are compared word by word. If 3 or more meaningful words match between two titles they are considered the same story and one is skipped.

**Layer 3 — Groq semantic dedup**
Before generating scripts, all article titles and previews are sent to Groq which identifies stories covering the same event from different sources. Only the most complete version is kept.

---

## Prompt design

Groq is prompted to write in a specific spoken style:

- Natural conversational English — never formal or written
- Every technical term explained with a real world analogy
- Short punchy sentences mixed with longer ones for rhythm
- Each story ends with a practical takeaway for developers
- No bullet points, no headers, no markdown in output
- Host name is Herlin — introduces herself once per episode only

---

## Known limitations

- Groq free tier has a 100k token daily limit — this supports 5 categories with 5 deep dives each comfortably
- Some articles behind hard paywalls return limited content — these get partial treatment with Groq filling context from its own knowledge
- GitHub Pages has storage limits — episodes older than 3 days are automatically deleted from storage (but remain in your podcast app after download)
- Kokoro TTS requires PyTorch — first run downloads the model (~300MB)

---
