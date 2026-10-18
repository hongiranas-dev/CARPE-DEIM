<div align="center">

# ✳️ FounderOS · Carpe Deim

**A multilingual, source-grounded startup copilot for Indian founders.**
Ask in Hindi, Tamil or English → get cited answers → research your market → match investors → draft pitches → execute with founder approval.

[🚀 Live Demo](https://carpe-deim-lpujuwux2gothufm4lmhdh.streamlit.app/) ·

</div>

---

## 💡 The Problem
Millions of Tier-2/3 founders think in their own language, but startup guidance (DPIIT, GST, MCA, investors) is English-only, scattered, and full of jargon. Generic chatbots hallucinate on compliance, and that costs founders real money.

## ✅ The Solution
FounderOS answers **only from retrieved official sources**, shows the citations, and refuses when evidence is insufficient. Nothing is fabricated, and nothing executes without founder approval.

## ✨ Features

| | Feature | What it does |
|---|---|---|
| 🧭 | **Startup Advisor** | RAG (ChromaDB) over official Startup India/DPIIT, CBIC & MCA sources, with Hindi/Hinglish retrieval support. Every answer shows its source passages and links. |
| 🎙️ | **Voice in / Voice out** | Sarvam STT transcribes Hindi / Tamil / English speech (editable before asking). Sarvam TTS reads answers back. |
| 📊 | **Market Research** | One founder profile produces a source-grounded brief: problem, customers, competitors, risks and assumptions. **No fabricated TAM.** |
| 🤝 | **Investor Matching** | Transparent scoring from published criteria only: sector 40%, stage 25%, cheque 20%, geography 15%. Each match links to its evidence. |
| ✉️ | **Pitch Drafts** | Personalized, editable email drafts per investor. Traction is included only if the founder provides it. |
| ⚙️ | **MCP Execution Layer** | A FastMCP server exposes `create_gmail_draft`, `append_to_sheet`, `create_calendar_followup`, each gated by explicit founder approval. |
| ⏱️ | **Agent Activity Log** | Shows only actions that actually happened. |

## 🏗️ Architecture

```
 Founder (Voice / Text: हिंदी · தமிழ் · English)
        │
        ▼
 Streamlit UI ──► Sarvam STT ──► editable transcript
        │
        ▼
 RAG Retriever (ChromaDB + source metadata)
        │  insufficient evidence? → refuse honestly
        ▼
 Sarvam LLM (answer from retrieved passages) ──► Sarvam TTS
        │
        ├──► Market Research ──► Investor Matching ──► Pitch Drafts
        │
        ▼
 MCP Client ──► FastMCP Server (founder-approved actions)
                 ├─ create_gmail_draft
                 ├─ append_to_sheet
                 └─ create_calendar_followup
```

## 🧱 Tech Stack
Python · Streamlit · ChromaDB · Sarvam AI (STT, LLM, TTS) · MCP / FastMCP

## 🛡️ Design Principles
- **Grounded, not guessed:** answers cite official sources, and the system refuses on weak evidence.
- **Human-in-the-loop:** MCP tools run only with explicit `approved=True`.
- **Honest by design:** unknown investor criteria are left unscored, currencies are never converted, and no email is ever sent.

## 🔍 Built vs. Simulated

| ✅ Built & working | 🎭 Demo-scoped (by design) |
|---|---|
| RAG over official sources with citations | Small curated corpus & verified-sample investor set |
| Sarvam STT/TTS/LLM integration | MCP tools write to **local files**, not live Gmail/Sheets/Calendar |
| Market brief, investor scoring, pitch drafts | Drafts only; no emails sent |
| FastMCP server + client with approval gate | Google OAuth is on the roadmap |

## 🚀 Run Locally

```bash
git clone https://github.com/hongiranas-dev/CARPE-DEIM.git
cd CARPE-DEIM
pip install -r requirements.txt
cp .env.example .env        # add SARVAM_API_KEY
streamlit run app.py
```

**MCP demo:**
```bash
python mcp_client_demo.py --approve
```
Outputs land in `data/demo_actions/`. **Tests:** `python -m unittest discover -s tests -v`

## 🗺️ Roadmap
- Real Gmail / Google Sheets / Calendar via OAuth
- Larger corpus (funding, market reports) and live investor data
- WhatsApp bot + more Indian languages

---
<div align="center">Built for founders who think in their own language. <b>Carpe deim.</b></div>
