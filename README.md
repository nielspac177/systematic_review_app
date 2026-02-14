# ReviewPyPer - Systematic Review App

An LLM-powered systematic review platform that automates study screening, data extraction, and risk of bias assessment following PRISMA 2020 guidelines.

**Two ways to use it** — a full-featured Python app (`app.py`) or a zero-install standalone HTML file (`ReviewPyPer_Standalone.html`).

---

## Features

| Feature | Description |
|---------|-------------|
| **Project Setup** | Define research question, generate PICO-based inclusion/exclusion criteria with AI |
| **Search Strategy Wizard** | AI-assisted PubMed search strategy generation with translation to SCOPUS, Web of Science, Cochrane, EMBASE |
| **Title/Abstract Screening** | Batch AI screening of imported references (CSV, RIS, NBIB, BibTeX) with confidence scores |
| **Full-text Screening** | Upload PDFs for full-text evaluation against criteria (with OCR for scanned PDFs) |
| **Feedback Review** | Re-review low-confidence exclusions to catch missed studies; manual override support |
| **Data Extraction** | AI extracts structured data fields from study full texts |
| **Risk of Bias** | AI-assisted assessment using RoB 2, ROBINS-I, Newcastle-Ottawa, or QUADAS-2, with traffic light visualization |
| **Cost Tracking** | Real-time API cost tracking across all operations |
| **Export** | CSV export on every results page |

---

## Option 1: Standalone HTML (No Installation)

**`ReviewPyPer_Standalone.html`** is a single file that runs entirely in your browser. No Python, no terminal, no dependencies to install.

### How to use

1. Open `ReviewPyPer_Standalone.html` in any modern browser (Chrome, Firefox, Safari, Edge)
2. Enter your **OpenAI** or **Anthropic** API key on the Setup page
3. Follow the workflow: Setup > Search Strategy > Screening > Extraction > Risk of Bias

### What's inside

- **PDF.js** (Mozilla) for text extraction from text-based PDFs
- **Tesseract.js** for OCR on scanned PDFs (runs in-browser via WebAssembly)
- **File parsers** for CSV, RIS, NBIB, and BibTeX formats built in JavaScript
- **localStorage** for session persistence (survives page refresh)
- Direct API calls to OpenAI or Anthropic from the browser

### Supported models

| Provider | Models |
|----------|--------|
| OpenAI | GPT-4o, GPT-4o-mini, GPT-4.1, GPT-4-turbo, GPT-3.5-turbo, GPT-5, GPT-5-mini |
| Anthropic | Claude Sonnet 4, Claude Opus 4, Claude 3.5 Sonnet, Claude 3.5 Haiku, Claude 3 Haiku |

### Notes

- Your API key is stored only in browser memory and **never saved to disk**
- PDF text extraction works best with text-based PDFs; scanned PDFs are OCR'd automatically (~30s per page)
- Project data persists in localStorage but will be lost if you clear browser data

---

## Option 2: Python App (Full Features)

**`app.py`** is a Streamlit multi-page application with additional capabilities including SQLite project storage, DOCX export, and audit logging.

### Installation

```bash
cd systematic_review_app
pip install -r requirements.txt
```

For OCR support (scanned PDFs), also install Tesseract:
```bash
# macOS
brew install tesseract

# Ubuntu/Debian
sudo apt-get install tesseract-ocr
```

### Running

```bash
streamlit run app.py
```

The app opens at `http://localhost:8501`.

### Additional features (Python only)

- **SQLite database** for persistent project storage across sessions
- **Audit trail** logging all LLM calls with prompts, responses, and costs
- **DOCX export** for detailed reports
- **RevMan XML export** for Cochrane integration
- **Fuzzy deduplication** of references across multiple databases
- **PRISMA flow diagram** with real-time count tracking
- **Budget enforcement** with configurable spending limits

### Configuration

Set your API key as an environment variable or enter it in the app:
```bash
export OPENAI_API_KEY="sk-..."
# or
export ANTHROPIC_API_KEY="sk-ant-..."
```

---

## Project Structure

```
systematic_review_app/
├── ReviewPyPer_Standalone.html  # Zero-install browser version
├── app.py                       # Streamlit entry point
├── requirements.txt             # Python dependencies
├── config/
│   └── settings.py              # App configuration
├── pages/                       # Streamlit pages (0-8)
├── components/                  # Reusable UI components
└── core/                        # Backend logic
    ├── llm/                     # LLM clients, prompts, cost tracking
    ├── screening/               # Title/abstract & full-text screening
    ├── extraction/              # Data extraction
    ├── search_strategy/         # Search strategy building
    ├── file_parsers/            # CSV, RIS, NBIB, BibTeX, EndNote
    ├── pdf/                     # PDF text extraction + OCR
    ├── risk_of_bias/            # RoB assessment + templates
    ├── storage/                 # SQLite session management
    └── export/                  # DOCX export
```

---

## Which version should I use?

| | HTML | Python |
|---|---|---|
| **Setup** | Open in browser | Install Python + dependencies |
| **Best for** | Quick use, sharing, no-code users | Power users, large reviews, audit trails |
| **PDF OCR** | In-browser (Tesseract.js) | Native (pytesseract, faster) |
| **Data storage** | Browser localStorage | SQLite database |
| **Export** | CSV | CSV, DOCX, RevMan XML |
| **Offline** | After first load (CDNs cached) | Fully offline (except API calls) |

---

## Cost Awareness

Both versions use LLM APIs (OpenAI or Anthropic) which incur costs per API call. Estimated costs per study:

- Title/abstract screening: ~$0.001-0.005
- Full-text screening: ~$0.01-0.05
- Data extraction: ~$0.01-0.05
- Risk of bias: ~$0.01-0.05

Both versions show cost estimates before processing and track running totals.
