import re
import time
import textwrap
import requests
from bs4 import BeautifulSoup
from google import genai

client = genai.Client()
MODEL = "gemini-3-flash-preview"

MAX_SUMMARY_WORDS = 150
CHUNK_CHAR_SIZE = 15000
REQUEST_TIMEOUT = 10
MAX_RETRIES = 2


def fetch_page(url: str) -> str:
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
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {url} after {MAX_RETRIES + 1} attempts: {last_err}")


def extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = [ln.strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def chunk_text(text: str, size: int = CHUNK_CHAR_SIZE) -> list[str]:
    if len(text) <= size:
        return [text]
    return textwrap.wrap(text, size, break_long_words=False, replace_whitespace=False)


def llm_summarize(text: str, instruction: str) -> str:
    max_attempts = 4
    for attempt in range(max_attempts):
        try:
            resp = client.models.generate_content(
                model=MODEL,
                contents=f"{instruction}\n\nTEXT:\n{text}",
            )
            return resp.text.strip()
        except Exception as e:
            is_rate_limit = "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e)
            if is_rate_limit and attempt < max_attempts - 1:
                wait_time = 20 * (attempt + 1)
                print(f"Rate limit hit, waiting {wait_time}s before retry ({attempt + 1}/{max_attempts})...")
                time.sleep(wait_time)
            else:
                raise
    raise RuntimeError("Failed after max retries")


def enforce_length_guardrail(summary: str, max_words: int = MAX_SUMMARY_WORDS) -> str:
    words = summary.split()
    if len(words) <= max_words:
        return summary
    compressed = llm_summarize(
        summary,
        f"This summary is too long. Rewrite it in under {max_words} words, keeping only the most important points."
    )
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
        partial_summaries = [
            llm_summarize(c, "Summarize the key points of this section in 2-3 sentences.")
            for c in chunks
        ]
        combined = "\n".join(partial_summaries)
        raw_summary = llm_summarize(
            combined,
            f"Combine these section summaries into a single coherent summary under {MAX_SUMMARY_WORDS} words."
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