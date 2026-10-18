# FounderOS · Carpe deim

Local-first multilingual startup copilot MVP for Indian founders. Accessibility in mind.

## Current MVP checklist

- [x] Phase 1: initial Streamlit interface starts locally
- [x] Phase 2: official-source retrieval with ChromaDB and source metadata
- [x] Phase 2: Sarvam V1 client and missing-key handling
- [x] Phase 2: retrieval and metadata tests
- [ ] Sarvam answer generation: live calls are paused until hackathon credits are available
- [x] Local market research, evidence-based investor matching, and personalized pitch drafts
- [x] Local-only FastMCP execution tools with founder approval

## Run locally

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

The interface and local retrieval launch without AI credentials. For generated answers, copy `.env.example` to `.env`, add your Sarvam API key, then restart the app. Never commit `.env`.

The advisor retrieves official-source passages from Startup India/DPIIT, CBIC, and MCA before answering. Its small bundled corpus includes Hindi/Hinglish retrieval translations; citations link to the original official pages. Local Chroma data is stored in `.chroma/` and is ignored by Git.

The Market Research tab builds a deterministic brief from founder inputs and available retrieved official material. Since this corpus is primarily about compliance, it does not claim market sizing or competitor research that it cannot support. Investor matching reads `data/investors.csv`, which contains sourced profiles labeled `VERIFIED SAMPLE`; undisclosed criteria remain unscored. Cheque currencies are not converted. Pitch Drafts are editable local templates; no email is sent.

Run tests (no Sarvam API calls are made):

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## MCP local/demo tools

Install the dependencies from `requirements.txt`, then start the stdio MCP server with:

```powershell
.\.venv\Scripts\python.exe mcp_server.py
```

The server waits for an MCP client over standard input/output. For a complete client/server demo using an investor selected by the existing ranking code and a pitch created by the existing draft generator, run:

```powershell
.\.venv\Scripts\python.exe mcp_client_demo.py --approve
```

`--approve` is the founder's explicit approval to write the three local demo artifacts. Without it, the client refuses to execute. The tools save drafts to `data/demo_actions/email_drafts.jsonl`, investor rows to `data/demo_actions/investor_sheet.csv`, and reminders to `data/demo_actions/followups.jsonl`. These are local demo files only: they do not connect to Gmail, Google Sheets, or Google Calendar, and no email is sent. Demo action files are git-ignored. Real Google services would require configuring Google OAuth credentials and authorization; that setup is not needed for this MVP.

Run the retrieval tests with:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
