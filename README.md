# Agentic Architect Challenge — Submission

This repo contains my solutions to all three parts of the challenge.

```
├── part1_design/
│   ├── architecture.md       # architecture write-up (source)
│   ├── architecture.pdf      # 1-page architecture doc
│   └── Pipeline Diagram.png  # visual pipeline diagram
├── part2_scraper/
│   ├── scraper.py
│   └── requirements.txt
└── part3_agent/
    ├── agent.py
    ├── sample_document.txt
    └── requirements.txt
```

## Setup

1. Create and activate a virtual environment:
   ```
   python -m venv venv
   venv\Scripts\activate        # Windows
   source venv/bin/activate     # macOS/Linux
   ```

2. Get a free Gemini API key at https://aistudio.google.com/apikey

3. Set the API key as an environment variable:
   ```
   $env:GEMINI_API_KEY = "your_key_here"    # PowerShell
   export GEMINI_API_KEY="your_key_here"    # macOS/Linux
   ```

## Part 2 — Web scraper

```
cd part2_scraper
pip install -r requirements.txt
python scraper.py https://example.com
```

Fetches a page, cleans the HTML, and summarizes it with Gemini. Long pages are
split into chunks and summarized with a map-reduce approach so the model
never sees more text than it can handle well. A length guardrail keeps the
final summary under 150 words. API calls automatically retry with backoff if
they hit a rate limit.

## Part 3 — Agent with memory and tool use

```
cd part3_agent
pip install -r requirements.txt
python agent.py
```

Answers questions grounded only in `sample_document.txt`, remembers earlier
turns in the conversation, and calls a calculator tool on its own whenever a
question needs arithmetic.

## Part 1 — System design

See `part1_design/architecture.pdf` for the full write-up, and
`part1_design/Pipeline Diagram.png` for the visual pipeline. In short: a
guardrail agent checks for critical issues and contact history before
anything else runs; only non-critical emails proceed to classification and
RAG-grounded drafting; every draft goes through human review before sending.
