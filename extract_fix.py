"""Quick test to verify URL extraction fix works"""
from urllib.parse import unquote
import re

def decode_tldr_url(url: str) -> str:
    """
    TLDR wraps all links in tracking URLs like:
    https://tracking.tldrnewsletter.com/CL0/https:%2F%2Factualsite.com/...
    
    We decode the real URL from inside.
    """
    # Check if it's a TLDR tracking URL
    if "tracking.tldrnewsletter.com/CL0/" in url:
        # Extract the encoded URL after /CL0/
        parts = url.split("/CL0/")
        if len(parts) > 1:
            # Get everything before the /1/ counter
            encoded = parts[1].split("/1/")[0]
            # Decode percent encoding
            decoded = unquote(encoded)
            return decoded
    return url

# Test with real URLs from your email
test_urls = [
    "https://tracking.tldrnewsletter.com/CL0/https:%2F%2Fwww.testingcatalog.com%2Fmoonshot-ai-launches-kimi-k2-6-on-kimi-chat-and-apis%2F%3Futm_source=tldrai/1/0100019db041bf8f",
    "https://tracking.tldrnewsletter.com/CL0/https:%2F%2Fdevelopers.openai.com%2Fcodex%2Fmemories%2Fchronicle%3Futm_source=tldrai/1/0100019db041bf8f",
    "https://tracking.tldrnewsletter.com/CL0/https:%2F%2Fwww.anthropic.com%2Fnews%2Fanthropic-amazon-compute%3Futm_source=tldrai/1/0100019db041bf8f",
    "https://tracking.tldrnewsletter.com/CL0/https:%2F%2Ftessl.io%2Fblog%2Fgoogle-adds-subagents-to-gemini-cli/1/0100019db041bf8f",
]

print("Decoded URLs:")
for url in test_urls:
    decoded = decode_tldr_url(url)
    print(f"\n  Original : {url[:70]}...")
    print(f"  Decoded  : {decoded}")
