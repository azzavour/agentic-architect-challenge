"""
Web scraper + summarizer with fixes for the two original bottlenecks:

  1. Complex pages (JS-heavy, slow, or erroring) -> requests with timeout/retries
     + graceful fallback instead of hanging or crashing.
  2. Long content -> chunking + map-reduce summarization instead of dumping the
     whole page into one LLM call (which either fails on context limits or
     produces a bloated, unfocused summary).

Guardrail: the final summary is always re-checked against a max word count;
if the model overshoots, it is asked to compress once more before returning.
"""

import re
import time
import textwrap
import requests
from bs4 import BeautifulSoup
from google import genai

client = genai.Client()  # reads GEMINI_API_KEY from env
MODEL = "gemini-flash-latest"

MAX_SUMMARY_WORDS = 150       # guardrail: hard ceiling on final summary length
CHUNK_CHAR_SIZE = 8000        # ~ keeps each chunk comfortably within context
REQUEST_TIMEOUT = 10          # seconds; fixes the "hangs on slow pages" bug
MAX_RETRIES = 2


def fetch_page(url: str) -> str:
    """Fetch a page with timeout + retry. Returns raw HTML or raises on final failure."""
    last_err = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = requests.get(
                url,
                timeout=REQUEST_TIMEOUT,
                headers={"User-Agent": "Mozilla/5.0 (compatible; SupportBot/1.0)"},
            )
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))  # backoff
    raise RuntimeError(f"Failed to fetch {url} after {MAX_RETRIES + 1} attempts: {last_err}")


def extract_text(html: str) -> str:
    """Strip scripts/styles/nav/footer noise and return clean readable text."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    # collapse excessive whitespace/blank lines
    lines = [ln.strip() for ln in text.splitlines()]
    text = "\n".join(ln for ln in lines if ln)
    return text


def chunk_text(text: str, size: int = CHUNK_CHAR_SIZE) -> list[str]:
    """Split long text into manageable chunks. This is the fix for the
    'fails on long content' bottleneck: instead of one giant prompt, we
    summarize piece by piece, then summarize the summaries (map-reduce)."""
    if len(text) <= size:
        return [text]
    return textwrap.wrap(text, size, break_long_words=False, replace_whitespace=False)


def llm_summarize(text: str, instruction: str) -> str:
    resp = client.models.generate_content(
        model=MODEL,
        contents=f"{instruction}\n\nTEXT:\n{text}",
    )
    return resp.text.strip()


def enforce_length_guardrail(summary: str, max_words: int = MAX_SUMMARY_WORDS) -> str:
    """Guardrail: if the summary still exceeds the word cap after generation,
    force a single compression pass rather than silently truncating mid-sentence."""
    words = summary.split()
    if len(words) <= max_words:
        return summary
    compressed = llm_summarize(
        summary,
        f"This summary is too long. Rewrite it in under {max_words} words, "
        f"keeping only the most important points."
    )
    # final hard safety net: truncate if the model still overshoots
    words2 = compressed.split()
    if len(words2) > max_words:
        compressed = " ".join(words2[:max_words]) + "..."
    return compressed


def summarize_url(url: str) -> str:
    html = fetch_page(url)
    text = extract_text(html)

    if not text:
        return "No readable text content could be extracted from this page."

    chunks = chunk_text(text)

    if len(chunks) == 1:
        raw_summary = llm_summarize(
            chunks[0],
            f"Summarize the key points of this webpage in under {MAX_SUMMARY_WORDS} words."
        )
    else:
        # Map step: summarize each chunk independently
        partial_summaries = [
            llm_summarize(c, "Summarize the key points of this section in 2-3 sentences.")
            for c in chunks
        ]
        # Reduce step: summarize the summaries into one coherent final summary
        combined = "\n".join(partial_summaries)
        raw_summary = llm_summarize(
            combined,
            f"Combine these section summaries into a single coherent summary "
            f"under {MAX_SUMMARY_WORDS} words."
        )

    return enforce_length_guardrail(raw_summary)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python scraper.py <url>")
        sys.exit(1)
    try:
        print(summarize_url(sys.argv[1]))
    except RuntimeError as e:
        print(f"Error: {e}")