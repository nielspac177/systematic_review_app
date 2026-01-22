# Systematic Review App - Development Notes

## Overview

A Streamlit web application for conducting systematic reviews using LLM-powered screening and data extraction. Supports both OpenAI and Anthropic Claude models.

**Last Updated:** January 2025

---

## Quick Start

```bash
# Navigate to project
cd "/Users/nielspacheco/Desktop/Research/Rolston lab/Review_pyper_v2/Calvinwhow-ReviewPyper-5bf1f7a/systematic_review_app"

# Activate virtual environment
source venv/bin/activate

# Run the app
streamlit run app.py
```

App runs at: `http://localhost:8501`

---

## Architecture

```
systematic_review_app/
├── app.py                      # Main Streamlit entry point
├── requirements.txt            # Python dependencies
├── DEVELOPMENT_NOTES.md        # This file
│
├── pages/                      # Streamlit multi-page app
│   ├── 1_Setup_Review.py       # Project setup, LLM config, criteria generation
│   ├── 2_Title_Abstract_Screening.py  # Upload CSV, screen studies
│   ├── 3_Fulltext_Screening.py # PDF upload and full-text screening
│   ├── 4_Feedback_Review.py    # Re-review low-confidence decisions
│   ├── 5_Extraction_Setup.py   # Configure data extraction fields
│   └── 6_Data_Extraction.py    # Extract data from included studies
│
├── core/                       # Backend logic
│   ├── llm/
│   │   ├── base_client.py      # Abstract LLM interface
│   │   ├── openai_client.py    # OpenAI GPT client (with retry on rate limit)
│   │   ├── anthropic_client.py # Anthropic Claude client
│   │   ├── prompts.py          # All prompt templates
│   │   ├── cost_tracker.py     # Cost estimation and budget tracking
│   │   └── rate_limit.py       # Rate limiting utilities (optional)
│   │
│   ├── screening/
│   │   ├── criteria_generator.py   # LLM-assisted PICO criteria generation
│   │   ├── title_abstract.py       # Title/abstract screening logic
│   │   ├── fulltext.py             # Full-text screening logic
│   │   └── feedback.py             # Feedback loop for low-confidence decisions
│   │
│   ├── extraction/
│   │   ├── field_recommender.py    # LLM recommends extraction fields
│   │   └── data_extractor.py       # Extract data from PDFs
│   │
│   ├── pdf/
│   │   └── processor.py            # PDF text extraction (direct + OCR)
│   │
│   └── storage/
│       ├── models.py               # Pydantic data models
│       ├── session_manager.py      # SQLite-backed project storage
│       └── audit_logger.py         # LLM call audit trail
│
├── components/                 # Reusable UI components
│   ├── prisma_diagram.py       # PRISMA 2020 flow diagram
│   ├── progress_bar.py         # Progress tracking UI
│   └── cost_display.py         # Cost estimation display
│
├── config/
│   └── settings.py             # App configuration
│
└── venv/                       # Virtual environment (don't commit to git)
```

---

## Features Implemented (MVP)

### 1. Project Setup (`pages/1_Setup_Review.py`)
- Create/load named projects
- User-specified storage folder
- LLM provider selection (OpenAI or Anthropic)
- Model selection (GPT-4o, GPT-4o-mini, Claude, etc.)
- Budget limit setting
- **LLM-assisted criteria generation** (PICO framework)

### 2. Title/Abstract Screening (`pages/2_Title_Abstract_Screening.py`)
- CSV file upload
- Column mapping (Title, Abstract, PMID, DOI)
- Cost estimation before screening
- Real-time progress tracking
- **PICO-based exclusion categories:**
  - Wrong population
  - Wrong intervention
  - Wrong comparator
  - Wrong outcome
  - Wrong study design
  - Other
- Confidence scores (0.0 - 1.0)
- Export results (CSV)
- Session state caching to prevent duplicate API calls

### 3. Full-text Screening (`pages/3_Fulltext_Screening.py`)
- PDF batch upload
- Dual extraction (direct + OCR, uses better result)
- Screen against criteria

### 4. Feedback Review (`pages/4_Feedback_Review.py`)
- Re-review excluded studies with confidence < 0.8
- LLM reconsiders with inclusive prompt
- User can confirm/override

### 5. Data Extraction (`pages/5_Extraction_Setup.py`, `pages/6_Data_Extraction.py`)
- LLM recommends extraction fields
- Custom field configuration
- Extract from PDFs
- Missing data marked as "NR" (Not Reported)
- Export to CSV/Excel

### 6. Supporting Features
- **Cost tracking:** Estimate upfront, track actual spend, budget limits
- **PRISMA 2020 diagram:** Auto-updates at each phase
- **Audit trail:** Logs all LLM calls (prompt, response, decision, cost)
- **Rate limit handling:** Auto-retry when hitting OpenAI limits

---

## Key Technical Decisions

### Rate Limiting (Simple Approach)
The OpenAI client uses a simple retry mechanism:
- Makes API calls directly (fast)
- If rate limited → waits the time OpenAI specifies → retries (up to 5 times)
- No pre-emptive throttling

Located in: `core/llm/openai_client.py`

### Model Recommendation
- **GPT-4o-mini**: Best for screening (fast, cheap, accurate enough)
- **GPT-4o**: Use for complex criteria generation if needed
- **Claude 3.5 Sonnet**: Good alternative, different rate limits

### Session State Caching
The screening page caches results to prevent duplicate API calls on Streamlit reruns:
- Study hash validation
- Screening lock to prevent concurrent execution
- Screener instance persistence

---

## Database Schema (SQLite)

Projects are stored in SQLite at the user-specified storage folder:

```sql
-- Main tables
projects          -- Project metadata, criteria, settings
studies           -- Individual studies (title, abstract, PDF path)
screening_decisions -- Decisions with reasons and confidence
extraction_fields -- Configured extraction fields
extractions       -- Extracted data values
audit_log         -- All LLM calls for transparency
cost_tracking     -- Cost per operation
```

---

## Environment Variables (Optional)

```bash
# OpenAI
OPENAI_API_KEY=sk-...

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Rate limiting (optional tuning)
OPENAI_TPM_LIMIT=90000          # Tokens per minute
SCREENING_MAX_ABSTRACT_CHARS=2000
SCREENING_MAX_TITLE_CHARS=300
```

---

## Deployment (Streamlit Community Cloud)

1. Push to GitHub (exclude `venv/`)
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect repo, select `app.py`
4. Deploy

**Required `.gitignore`:**
```
venv/
__pycache__/
*.pyc
.env
*.db
```

---

## Future Features (Post-MVP)

### Planned
- [ ] Rapid review mode (skip feedback loop, title-only option)
- [ ] Scoping review mode (PCC framework instead of PICO)
- [ ] Risk of bias assessment (customizable domains)
- [ ] Dual-reviewer simulation (run twice, calculate agreement)
- [ ] Multi-search merging (combine CSVs from different databases)
- [ ] Auto-translation (detect and translate non-English abstracts)
- [ ] Batch processing with configurable delays
- [ ] Local model support (Ollama)

### Nice to Have
- [ ] Export to Excel with formatting
- [ ] PRISMA diagram export as image
- [ ] Study deduplication
- [ ] Reference management integration

---

## Troubleshooting

### "Rate limit exceeded" errors
- The app auto-retries, just wait
- Use GPT-4o-mini (higher rate limits)
- Check your OpenAI tier at platform.openai.com

### App is slow
- Make sure you're using GPT-4o-mini for screening
- Check network connection
- OpenAI API status: status.openai.com

### Import errors
```bash
source venv/bin/activate
pip install -r requirements.txt
```

---

## Contact / Resume Context

This app was built in a Claude Code session. To continue development:

1. Navigate to this directory
2. Run `claude` to start a new session
3. Reference this file for context
4. Or use `/compact` to get a summary of previous work

---

## Dependencies

Key packages (see `requirements.txt` for full list):
- `streamlit>=1.30.0` - Web interface
- `openai>=1.10.0` - OpenAI API
- `anthropic>=0.18.0` - Claude API
- `pandas>=2.0.0` - Data handling
- `pydantic>=2.0.0` - Data models
- `PyPDF2` - PDF text extraction
- `pytesseract` - OCR fallback
- `tiktoken` - Token counting
- `openpyxl` - Excel export
