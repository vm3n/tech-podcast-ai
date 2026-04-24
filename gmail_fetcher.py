"""
Stage 3 — Gmail Fetcher (complete final version)
- Decodes TLDR tracking URLs to get real article links
- Filters ads, tracking, and junk links
- Deduplicates by domain (max 2 per domain)
- Only processes 5 categories: ai, dev, tech, data, it
- Does NOT mark URLs as processed (main.py handles that)
"""

import os
import base64
import re
import urllib.parse
from datetime import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from database import setup_database, is_url_seen

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Only process these 5 categories
ALLOWED_CATEGORIES = {'ai', 'dev', 'tech', 'data', 'it'}

# Known ad/sponsor domains — skip entirely
AD_DOMAINS = {
    "qawolf.com", "boldsign.com", "stackadapt.com",
    "go.stackadapt.com", "airia.com", "zenity.io",
    "pages.awscloud.com", "advertise.tldr.tech",
    "jobs.ashbyhq.com", "labs.zenity.io",
    "googlecloudevents.com", "cal.com",
    "skills.google", "pointfive.co",
}

# Skip URLs containing these keywords
SKIP_KEYWORDS = [
    "unsubscribe", "optout", "opt-out",
    "advertise", "advertisement", "sponsor",
    ".png", ".jpg", ".gif", ".ico", ".svg",
    "pstmrk", "aweber", "w3.org",
    "open?m=", "confirm", "email/unsubscribe",
    "refer.tldr.tech", "a.tldrnewsletter.com",
    "links.tldrnewsletter.com", "images.tldr",
    "safelinks.protection.outlook",
    "tldr.tech/signup", "tldr.tech/ai",
    "tldr.tech/infosec", "tldr.tech/design",
    "tldr.tech/marketing", "tldr.tech/webdev",
    "tldr.tech/devops", "tldr.tech/it",
    "tldr.tech/dev", "tldr.tech/crypto",
    "tldr.tech/founders", "tldr.tech/product",
    "tldr.tech/data", "link.omane.media",
    "rh_ref=", "sl_campaign=", "myapp.localhost",
]


def get_gmail_service():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file(
            "token.json", SCOPES
        )
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def detect_category(sender_name: str) -> str:
    """
    Detects podcast category from sender name.
    TLDR AI -> ai
    TLDR Dev -> dev
    TLDR -> tech
    """
    name = sender_name.lower().strip()
    for prefix in ["tldr ", "the ", "newsletter "]:
        if name.startswith(prefix):
            name = name[len(prefix):]
    name = name.strip()
    name = re.sub(r'[^a-z0-9]', '-', name)
    if not name or name == "tldr":
        return "tech"
    return name


def decode_tldr_url(url: str) -> str:
    """
    Decodes TLDR tracking wrapper URLs.
    https://tracking.tldrnewsletter.com/CL0/https:%2F%2Factualsite.com/...
    becomes https://actualsite.com/...
    """
    if "tracking.tldrnewsletter.com/CL0/" in url:
        parts = url.split("/CL0/")
        if len(parts) > 1:
            encoded = parts[1].split("/1/")[0]
            return urllib.parse.unquote(encoded)
    return url


def get_domain(url: str) -> str:
    """Extracts clean domain from URL."""
    try:
        domain = urllib.parse.urlparse(url).netloc
        return domain.replace("www.", "")
    except Exception:
        return ""


def extract_links_from_email(body: str) -> list:
    """
    Extracts real article links from email body.
    1. Decodes TLDR tracking URLs
    2. Filters ads and junk
    3. Deduplicates by domain (max 2 per domain)
    4. Only keeps URLs with proper content paths
    """
    raw_urls = re.findall(
        r'https?://[^\s<>"{}|\\^`\[\]]+', body
    )

    clean_urls = []
    seen_urls = set()
    domain_count = {}

    for url in raw_urls:
        url = url.rstrip(".,;:)=")

        # Decode TLDR tracking URL
        decoded = decode_tldr_url(url)

        # Skip keywords in decoded URL
        if any(kw in decoded.lower() for kw in SKIP_KEYWORDS):
            continue

        # Skip duplicate URLs
        if decoded in seen_urls:
            continue

        # Must have content path (not bare domain)
        if decoded.count("/") < 3:
            continue

        # Get domain
        domain = get_domain(decoded)
        if not domain:
            continue

        # Skip ad domains
        if domain in AD_DOMAINS:
            continue

        # Max 2 URLs per domain to avoid ad repetition
        domain_count[domain] = domain_count.get(domain, 0) + 1
        if domain_count[domain] > 2:
            continue

        seen_urls.add(decoded)
        clean_urls.append(decoded)

    return clean_urls


def get_email_body(service, msg_id: str) -> str:
    """Gets full HTML or text body of an email."""
    try:
        message = service.users().messages().get(
            userId="me",
            id=msg_id,
            format="full"
        ).execute()

        payload = message.get("payload", {})
        parts = payload.get("parts", [])
        body = ""

        if parts:
            for part in parts:
                if part.get("mimeType") == "text/html":
                    data = part.get("body", {}).get("data", "")
                    if data:
                        body = base64.urlsafe_b64decode(
                            data
                        ).decode("utf-8", errors="ignore")
                        break
            if not body:
                for part in parts:
                    if part.get("mimeType") == "text/plain":
                        data = part.get("body", {}).get("data", "")
                        if data:
                            body = base64.urlsafe_b64decode(
                                data
                            ).decode("utf-8", errors="ignore")
                            break
        else:
            data = payload.get("body", {}).get("data", "")
            if data:
                body = base64.urlsafe_b64decode(
                    data
                ).decode("utf-8", errors="ignore")

        return body
    except Exception as e:
        print(f"  Error getting email body: {e}")
        return ""


def fetch_newsletter_links() -> dict:
    """
    Fetches all article links from emails tagged Podcasts.
    Only processes ALLOWED_CATEGORIES: ai, dev, tech, data, it
    Returns dict: {category: [urls]}
    Does NOT mark URLs as processed — main.py does that.
    """
    print("\n" + "="*50)
    print("GMAIL INGESTION")
    print("="*50)

    setup_database()
    service = get_gmail_service()

    query = "label:Podcasts newer_than:1d"
    print(f"\nSearching Gmail label:Podcasts...")
    print(f"Processing categories: {ALLOWED_CATEGORIES}")

    try:
        results = service.users().messages().list(
            userId="me",
            q=query,
            maxResults=50
        ).execute()
        messages = results.get("messages", [])
        print(f"Found {len(messages)} tagged emails")
    except Exception as e:
        print(f"Gmail API error: {e}")
        return {}

    category_links = {}
    today = datetime.now().strftime("%Y-%m-%d")

    for msg in messages:
        try:
            meta = service.users().messages().get(
                userId="me",
                id=msg["id"],
                format="metadata",
                metadataHeaders=["From", "Subject"]
            ).execute()

            headers = meta.get("payload", {}).get("headers", [])
            sender = ""
            subject = ""

            for header in headers:
                if header["name"] == "From":
                    sender = header["value"]
                if header["name"] == "Subject":
                    subject = header["value"]

            # Skip confirmation emails
            if "confirm" in subject.lower():
                print(f"\n  Skipping confirmation: {subject[:50]}")
                continue

            sender_name = sender.split("<")[0].strip()
            category = detect_category(sender_name)

            # Only process allowed categories
            if category not in ALLOWED_CATEGORIES:
                print(f"\n  Skipping {category} — not in allowed categories")
                continue

            print(f"\n  Newsletter : {subject[:50]}")
            print(f"  Sender     : {sender_name}")
            print(f"  Category   : {category}")

            body = get_email_body(service, msg["id"])
            if not body:
                continue

            links = extract_links_from_email(body)
            print(f"  Links found: {len(links)}")

            for i, link in enumerate(links[:3], 1):
                print(f"    {i}. {link[:80]}")

            new_links = []
            for link in links:
                if not is_url_seen(link, days=7):
                    new_links.append(link)

            print(f"  New links  : {len(new_links)}")

            if category not in category_links:
                category_links[category] = []
            category_links[category].extend(new_links)

        except Exception as e:
            print(f"  Error: {e}")
            continue

    print(f"\n{'='*50}")
    print("INGESTION SUMMARY")
    print(f"{'='*50}")
    for cat, links in category_links.items():
        print(f"  {cat:15} : {len(links)} links")
    print(f"{'='*50}")

    return category_links


if __name__ == "__main__":
    categories = fetch_newsletter_links()
    print("\nFinal article URLs per category:")
    for cat, links in categories.items():
        print(f"\n  [{cat.upper()}]")
        for i, link in enumerate(links[:5], 1):
            print(f"    {i}. {link}")
