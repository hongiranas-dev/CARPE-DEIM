"""FounderOS: local-first startup copilot MVP."""

import os
import mimetypes
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from rag import has_sufficient_evidence, retrieve
from market_research import generate_market_summary
from sarvam_client import SarvamConfigurationError, SarvamRequestError, generate_answer
from sarvam_voice import SarvamVoiceError, synthesize_speech, transcribe_audio
from startup_workflow import prepare_startup_workflow


load_dotenv(Path(__file__).resolve().parent / ".env")


@st.cache_data(show_spinner=False, ttl=3600)
def cached_generation(user_question: str, evidence: list[dict]) -> str:
    return generate_answer(user_question, evidence)


@st.cache_data(show_spinner=False, ttl=3600)
def cached_synthesis(answer: str, language_code: str) -> tuple[bytes, dict]:
    return synthesize_speech(answer, language_code)


@st.cache_data(show_spinner=False, ttl=3600)
def cached_market_summary(startup: dict, report: dict) -> dict:
    return generate_market_summary(startup, report)


def get_advisor_result(user_question: str) -> dict:
    """Shared RAG and answer path for typed and transcribed questions."""
    try:
        passages = retrieve(user_question)
    except Exception as exc:
        return {"question": user_question, "status": "retrieval_error", "error": str(exc), "passages": []}
    if not has_sufficient_evidence(passages):
        return {"question": user_question, "status": "insufficient_evidence", "passages": passages, "answer": None}
    api_key = os.getenv("SARVAM_API_KEY", "").strip()
    if not api_key or api_key == "your_sarvam_api_key_here":
        return {"question": user_question, "status": "sarvam_not_configured", "passages": passages, "answer": None}
    try:
        answer = cached_generation(user_question, passages)
        return {"question": user_question, "status": "generated", "passages": passages, "answer": answer}
    except SarvamConfigurationError as exc:
        return {"question": user_question, "status": "sarvam_not_configured", "passages": passages, "answer": None, "error": str(exc)}
    except SarvamRequestError as exc:
        return {"question": user_question, "status": "generation_error", "passages": passages, "answer": None, "error": str(exc)}


def _audio_content_type(uploaded_file) -> str:
    content_type = getattr(uploaded_file, "type", None)
    if content_type and content_type != "application/octet-stream":
        return content_type
    extension_types = {
        ".wav": "audio/wav", ".mp3": "audio/mpeg", ".aac": "audio/aac", ".aiff": "audio/aiff",
        ".ogg": "audio/ogg", ".opus": "audio/opus", ".flac": "audio/flac", ".mp4": "audio/mp4",
        ".m4a": "audio/mp4", ".amr": "audio/amr", ".webm": "audio/webm",
    }
    suffix = Path(getattr(uploaded_file, "name", "")).suffix.lower()
    return extension_types.get(suffix) or mimetypes.guess_type(getattr(uploaded_file, "name", ""))[0] or ""


def render_advisor_result(result: dict) -> None:
    """Render evidence links and answer consistently for typed and spoken questions."""
    if result["status"] == "retrieval_error":
        st.error(f"Document retrieval failed: {result['error']}")
        return
    if result["status"] == "insufficient_evidence":
        st.warning("I couldn’t find enough relevant evidence in the current source collection to answer reliably.")
        return

    passages = result["passages"]
    st.caption(f"Question: {result['question']}")
    st.markdown("#### Retrieved guidance")
    for index, passage in enumerate(passages, start=1):
        with st.expander(f"[{index}] {passage['title']} · {passage['publisher']}", expanded=index == 1):
            st.caption(f"{passage['passage_type'].replace('_', ' ').title()} · {passage['language'].upper()}")
            st.write(passage["text"])
            st.markdown(f"[Open source document]({passage['source_url']})")

    if result["status"] == "sarvam_not_configured":
        st.info("Retrieved source passages are ready. Add SARVAM_API_KEY to your project .env file to generate an answer.")
        return
    if result["status"] == "generation_error":
        st.error(result["error"])
        return

    answer = result["answer"]
    st.markdown("#### Advisor response")
    st.markdown(answer)
    language_code = st.session_state.get("voice_language_code", "hi-IN")
    if st.button("🔊 Speak this answer", key="speak_advisor_answer"):
        try:
            audio_bytes, metadata = cached_synthesis(answer, language_code)
            st.session_state["advisor_speech"] = {
                "answer": answer,
                "language_code": language_code,
                "audio": audio_bytes,
                "metadata": metadata,
            }
            st.session_state.setdefault("activity_events", []).append("Generated spoken advisor answer with Sarvam TTS.")
        except (ValueError, SarvamVoiceError) as exc:
            st.error(f"Could not generate spoken answer: {exc}")

    speech = st.session_state.get("advisor_speech")
    if speech and speech["answer"] == answer and speech["language_code"] == language_code:
        st.audio(speech["audio"], format=speech["metadata"]["mime_type"])


st.set_page_config(page_title="FounderOS | Carpe deim", page_icon="✳️", layout="wide")

st.markdown(
    """
    <style>
    .block-container {max-width: 1180px; padding-top: 2.2rem;}
    [data-testid="stSidebar"] {border-right: 1px solid #e8e9ed;}
    .eyebrow {color:#6558d3; font-size:.78rem; font-weight:700; letter-spacing:.12em; text-transform:uppercase;}
    .hero {font-size:2.4rem; font-weight:750; letter-spacing:-.045em; margin:.1rem 0 .25rem; color:#171923;}
    .muted {color:#686c78; font-size:1rem;}
    .status {background:#f4f3ff; border:1px solid #e3e0ff; padding:1rem 1.1rem; border-radius:12px;}
    </style>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("## ✳️ FounderOS")
    st.caption("Carpe deim · Startup copilot")
    st.divider()
    st.markdown("**Workspace**")
    st.markdown("🧭 Startup Advisor")
    st.markdown("📊 Market Research")
    st.markdown("🤝 Investor Matching")
    st.markdown("✉️ Pitch Drafts")
    st.divider()
    st.caption("PHASE 2 · Text advisor")
    st.caption("Answers use retrieved sources")

st.markdown('<div class="eyebrow">Your startup copilot</div>', unsafe_allow_html=True)
st.markdown('<div class="hero">Make your next move count.</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="muted">Practical answers, grounded research, and founder-approved next steps — in the language you think in.</div>',
    unsafe_allow_html=True,
)
st.write("")

advisor, market, investors, pitches, activity = st.tabs(
    ["🧭  Startup Advisor", "📊  Market Research", "🤝  Investor Matching", "✉️  Pitch Drafts", "⏱️  Agent Activity Log"]
)

with advisor:
    st.subheader("Ask your startup question")
    st.caption("Type or speak in English, हिंदी, or தமிழ். Retrieved official sources are shown with each answer.")
    with st.form("advisor_form"):
        question = st.text_area(
            "Question",
            placeholder="E.g. What are the steps to get DPIIT recognition for my startup?",
            label_visibility="collapsed",
            height=115,
            key="advisor_text_question",
        )
        submitted = st.form_submit_button("Get guidance →", type="primary")

    if submitted:
        if not question.strip():
            st.warning("Enter a question to get started.")
        else:
            with st.spinner("Searching official startup guidance…"):
                st.session_state["advisor_result"] = get_advisor_result(question.strip())

    st.markdown("#### Ask by voice")
    language_options = {"Hindi · हिंदी": "hi-IN", "English": "en-IN", "Tamil · தமிழ்": "ta-IN"}
    selected_language = st.selectbox("Voice language", list(language_options), key="voice_language")
    voice_language_code = language_options[selected_language]
    st.session_state["voice_language_code"] = voice_language_code

    record_audio = getattr(st, "audio_input", None)
    if record_audio is not None:
        recorded_file = record_audio("Record a question", key="advisor_audio_recording")
    else:
        recorded_file = None
        st.caption("Microphone recording is unavailable in this Streamlit version; upload an audio clip instead.")
    uploaded_file = st.file_uploader(
        "Or upload an audio clip",
        type=["wav", "mp3", "aac", "aiff", "ogg", "opus", "flac", "mp4", "m4a", "amr", "webm"],
        key="advisor_audio_upload",
    )
    audio_file = recorded_file if recorded_file is not None else uploaded_file
    if st.button("Transcribe audio →", key="transcribe_advisor_audio"):
        if audio_file is None:
            st.warning("Record or upload an audio clip before transcribing.")
        else:
            try:
                transcript = transcribe_audio(
                    audio_file.getvalue(),
                    getattr(audio_file, "name", None) or "recording.wav",
                    _audio_content_type(audio_file),
                    language_code=voice_language_code,
                )
                st.session_state["voice_transcript"] = transcript
                st.session_state.setdefault("activity_events", []).append("Transcribed founder audio with Sarvam STT.")
            except (ValueError, SarvamVoiceError) as exc:
                st.error(f"Audio transcription failed: {exc}")

    if "voice_transcript" in st.session_state:
        with st.form("transcribed_question_form"):
            edited_transcript = st.text_area(
                "Review and edit the transcription before asking",
                key="voice_transcript",
                height=110,
            )
            voice_submitted = st.form_submit_button("Get guidance from transcript →", type="primary")
        if voice_submitted:
            if not edited_transcript.strip():
                st.warning("Enter or correct the transcription before requesting guidance.")
            else:
                with st.spinner("Searching official startup guidance…"):
                    st.session_state["advisor_result"] = get_advisor_result(edited_transcript.strip())

    result = st.session_state.get("advisor_result")
    if result:
        st.divider()
        render_advisor_result(result)

    st.caption("Answers are grounded in the retrieved official-source passages shown below them.")

with market:
    st.subheader("Understand your market")
    st.caption("One profile prepares a source-grounded brief, an optional cached Sarvam narrative, investor matches, and editable email drafts.")
    with st.form("startup_workflow_form"):
        col1, col2 = st.columns(2)
        startup_name = col1.text_input("Startup name", placeholder="Your company or working name")
        founder_name = col2.text_input("Founder name", placeholder="Your name")
        description = st.text_area("Startup description / problem", placeholder="What problem are you solving, for whom, and how?", height=100)
        col1, col2, col3 = st.columns(3)
        sector = col1.selectbox("Sector", ["Agriculture", "Climate", "DeepTech / AI", "Education", "Fintech", "Health", "SaaS / Enterprise", "Consumer / Commerce", "Mobility / EV", "Other"])
        stage = col2.selectbox("Stage", ["Idea", "Pre-seed", "Seed", "Post-seed", "Pre-Series A", "Series A", "Series B", "Growth"])
        geography = col3.text_input("Geography", value="India", help="Include a country, e.g. Pune, India. Matches use the country stated in investor profiles.")
        target_customers = st.text_input("Target customers", placeholder="e.g. small retail pharmacies in Tier-2 cities")
        col1, col2 = st.columns([2, 1])
        business_model = col1.text_input("Proposed business model (optional)", placeholder="Who pays, and for what?")
        competitors = col2.text_input("Known competitors (optional)", placeholder="Founder-listed; not verified")
        traction = st.text_input("Actual traction (optional)", placeholder="Only enter verified figures or milestones")
        col1, col2, col3 = st.columns([1.4, 1, 1.5])
        funding_amount = col1.number_input("Funding ask (optional; 0 = omit)", min_value=0.0, value=0.0, step=0.1)
        funding_currency = col2.selectbox("Ask currency", ["USD million", "INR crore"])
        women_led = col3.checkbox("Woman CEO (required for CXXO matches)")
        submitted = st.form_submit_button("Prepare research, matches & drafts →", type="primary")

    if submitted:
        if not description.strip():
            st.warning("Add a short startup description before preparing the workflow.")
        else:
            profile = {
                "startup_name": startup_name.strip(),
                "founder_name": founder_name.strip(),
                "description": description.strip(),
                "sector": sector,
                "stage": stage,
                "geography": geography.strip(),
                "target_customers": target_customers.strip(),
                "business_model": business_model.strip(),
                "competitors": competitors.strip(),
                "traction": traction.strip(),
                "funding_amount": funding_amount if funding_amount > 0 else None,
                "funding_currency": funding_currency,
                "women_led": women_led,
            }
            with st.spinner("Retrieving local sources and preparing the brief…"):
                workflow = prepare_startup_workflow(profile)
                workflow["market_summary"] = cached_market_summary(profile, workflow["report"])
            st.session_state["workflow_results"] = workflow
            st.session_state.setdefault("activity_events", []).append("Prepared source-grounded research, ranked published investor profiles, and generated local draft emails.")
            st.success("Workflow prepared. Open the Investor Matching and Pitch Drafts tabs to review the results.")

    results = st.session_state.get("workflow_results")
    if results:
        report = results["report"]
        st.markdown("#### Market research brief")
        st.caption("Founder inputs are hypotheses. Market claims below are limited to retrieved sources; no TAM is fabricated.")
        summary = results.get("market_summary", {})
        if summary.get("status") == "generated":
            st.markdown("#### AI-generated preliminary market analysis")
            st.markdown(summary["text"])
        elif summary.get("message"):
            st.info(summary["message"])
        st.markdown("**Problem statement**")
        st.write(report["problem_statement"])
        st.caption(report["problem_label"])
        st.markdown("**Target customers**")
        st.write(report["target_customers"])
        st.caption(report["customer_label"])
        st.markdown("**Competitor overview**")
        st.write(report["competitors"])
        st.caption(report["competitor_label"])
        st.markdown("**Market opportunity**")
        st.write(report["market_opportunity"])
        st.markdown("**Business model**")
        st.write(report["business_model"])
        st.caption(report["business_model_label"])
        st.markdown("**Risks and assumptions**")
        for risk in report["risks"]:
            st.markdown(f"- {risk}")
        st.markdown("**Verified source context**")
        st.caption(report["corpus_note"])
        if report["verified_context"]:
            for passage in report["verified_context"]:
                with st.expander(f"{passage['title']} · {passage['publisher']}"):
                    st.write(passage["text"])
                    st.markdown(f"[Open source]({passage['source_url']})")
        else:
            st.info("No relevant source was retrieved from the bundled official-source collection.")

with investors:
    st.subheader("Find relevant investors")
    st.caption("Small verified sample of investor profiles · ranking uses only published criteria")
    results = st.session_state.get("workflow_results")
    if not results:
        st.info("Enter a startup profile in Market Research, then prepare the workflow to see matches.")
    else:
        st.caption("Score weights: sector 40%, stage 25%, cheque 20%, geography 15%. Unknown or incomparable fields are omitted from that profile’s denominator; currencies are never converted.")
        for index, match in enumerate(results["matches"], start=1):
            with st.container(border=True):
                title_col, score_col = st.columns([4, 1])
                title_col.markdown(f"**{index}. {match['firm']}**")
                score_col.metric("Profile fit", f"{match['score']}%")
                st.caption(f"Sectors: {match['sectors']} · Stage: {match['startup_stage']} · Cheque: {match['cheque_size_range']} · Geography: {match['geography']}")
                st.caption(f"Published portfolio examples: {match['past_investments'] or 'Not listed'}")
                for reason in match["reasons"]:
                    st.markdown(f"- {reason}")
                st.markdown(f"[Investor website]({match['website']}) · [Investment criteria evidence]({match['evidence_url']}) · [Portfolio evidence]({match['investment_evidence_url']})")
                st.caption("Verified sample record · a profile-fit ranking, not an introduction or likelihood of funding.")

with pitches:
    st.subheader("Pitch drafts")
    st.caption("Personalized deterministic templates · no LLM call · no email is sent")
    results = st.session_state.get("workflow_results")
    if not results:
        st.info("Prepare the workflow from Market Research to generate investor-specific drafts.")
    else:
        for index, draft in enumerate(results["drafts"], start=1):
            with st.expander(f"{index}. Draft for {draft['investor']}", expanded=index == 1):
                subject = st.text_input("Subject", value=draft["subject"], key=f"pitch_subject_{index}")
                body = st.text_area("Email draft", value=draft["body"], height=300, key=f"pitch_body_{index}")
                st.caption("Review and edit before use. Traction is included only when you provided it; no email is sent by FounderOS.")
                st.download_button("Download draft (.txt)", f"Subject: {subject}\n\n{body}", file_name=f"pitch-{index}.txt", mime="text/plain", key=f"pitch_download_{index}")

with activity:
    st.subheader("Agent activity")
    st.caption("Actions will appear here as they actually happen.")
    events = st.session_state.get("activity_events", [])
    if events:
        for event in reversed(events):
            st.markdown(f"- **Local workflow completed:** {event}")
    else:
        st.info("No workflow activity yet. No external actions or emails are sent by this workflow.")

st.divider()
api_key = os.getenv("SARVAM_API_KEY", "").strip()
api_configured = bool(api_key and api_key != "your_sarvam_api_key_here")
st.markdown(
    f'<div class="status"><b>Setup status</b><br><span class="muted">Sarvam API: {"configured" if api_configured else "not configured (optional)"} · Local source retrieval: ready</span></div>',
    unsafe_allow_html=True,
)
