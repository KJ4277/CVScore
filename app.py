import datetime
import html
import os
import tempfile
import threading

import streamlit as st

try:
    for _name in ("GEMINI_API_KEY", "GEMINI_MODEL"):
        if _name in st.secrets and not os.environ.get(_name):
            os.environ[_name] = str(st.secrets[_name])
except Exception:
    pass

from extract import extract_text 
from scoring import review_cv

st.set_page_config(page_title="CV Score", page_icon="📄", layout="centered")

DAILY_CAP = 100      # total reviews per day across all visitors (protects your API quota)
SESSION_CAP = 5      # reviews per visitor session
MAX_CHARS = 20000    # longest CV text we will analyse

st.markdown("""
<style>
#MainMenu, footer, header {visibility: hidden;}
.block-container {max-width: 680px; padding-top: 3rem; padding-bottom: 4rem;}
.hero h1 {font-size: 2.4rem; font-weight: 700; margin: 0 0 6px; letter-spacing: -0.02em;}
.hero p {font-size: 1.05rem; color: #5C6B80; margin: 0 0 24px;}
.pct {font-size: 4rem; font-weight: 700; line-height: 1; margin-top: 28px;}
.pct span {font-size: 2rem; opacity: 0.6;}
.track {height: 16px; background: #E6EBF2; border-radius: 99px; overflow: hidden; margin: 14px 0 12px;}
.fill {height: 100%; width: var(--w); border-radius: 99px;
       animation: grow 1.4s cubic-bezier(.2,.8,.2,1) both;}
@keyframes grow {from {width: 0;} to {width: var(--w);}}
@media (prefers-reduced-motion: reduce) {.fill {animation: none;}}
.verdict {font-size: 1.05rem; color: #1B2A41;}
.verdict span {color: #5C6B80;}
.delta {display: inline-block; margin-top: 10px; padding: 3px 12px; border-radius: 99px;
        font-weight: 600; font-size: 0.9rem;}
.up {background: #E3F4EC; color: #1F8A5B;}
.down {background: #FBE7E4; color: #C0392B;}
.same {background: #E9EDF3; color: #5C6B80;}
.tip {padding: 14px 18px; border: 1px solid #E1E7EF; border-left: 4px solid #2F5BEA;
      border-radius: 10px; margin: 10px 0; background: #fff; line-height: 1.5; color: #1B2A41;}
.tip.top {border-left-color: #C0392B;}
.tip b {display: block; margin-bottom: 2px;}
.brow {display: flex; justify-content: space-between; margin: 12px 0 4px; font-weight: 500;}
.btrack {height: 8px; background: #E6EBF2; border-radius: 99px; overflow: hidden;}
.bfill {height: 100%; border-radius: 99px;}
.note {color: #8493A8; font-size: 0.85rem; margin-top: 48px;}
</style>
""", unsafe_allow_html=True)

_lock = threading.Lock()


@st.cache_resource
def usage():
    return {"day": datetime.date.today(), "count": 0}


def try_reserve_review() -> bool:
    """Count one review against today's cap. Returns False if the cap is reached."""
    with _lock:
        u = usage()
        today = datetime.date.today()
        if u["day"] != today:
            u["day"], u["count"] = today, 0
        if u["count"] >= DAILY_CAP:
            return False
        u["count"] += 1
        return True


def colour(pct):
    return "#1F8A5B" if pct >= 75 else "#C77700" if pct >= 50 else "#C0392B"


def verdict(p):
    if p >= 85:
        return "Interview-ready.", "Strong across the board. Polish the small things below."
    if p >= 70:
        return "Good, with clear wins available.", "A few targeted edits will lift it."
    if p >= 50:
        return "Needs work.", "The basics are there, but impact and detail are holding it back."
    return "Early draft.", "Start with the first few fixes below. They'll move the score most."


st.markdown(
    '<div class="hero"><h1>How strong is your CV?</h1>'
    '<p>Upload your CV as a PDF for a score out of 100 and clear, specific fixes.</p></div>',
    unsafe_allow_html=True,
)

if "reviews" not in st.session_state:
    st.session_state["reviews"] = 0

file = st.file_uploader("Upload your CV (PDF)", type=["pdf"], label_visibility="collapsed")

if file is not None and st.button("Score my CV", type="primary"):
    if st.session_state["reviews"] >= SESSION_CAP:
        st.warning("You've reached the review limit for this session. Please come back later.")
    else:
        path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
                f.write(file.read())
                path = f.name
            with st.spinner("Reading your CV..."):
                text = extract_text(path)
                if len(text.split()) < 30:
                    st.error("We couldn't find readable text. If your CV is a scan or an "
                             "image, export it as a text-based PDF and try again.")
                    st.stop()
                if not try_reserve_review():
                    st.warning("The site has reached its daily limit. Please try again tomorrow.")
                    st.stop()
                st.session_state["reviews"] += 1
                previous = st.session_state.get("score")
                result = review_cv(text[:MAX_CHARS])
            st.session_state["previous"] = previous
            st.session_state["result"] = result
            if result["percentage"] > 0:
                st.session_state["score"] = result["percentage"]
        except Exception as e:
            # st.stop() raises a special exception that must not be swallowed
            if type(e).__name__ in ("StopException", "RerunException"):
                raise
            print("Review failed:", repr(e))  # visible in the server logs only
            st.error("Something went wrong while reviewing your CV. Please try again in a moment.")
            st.stop()
        finally:
            if path and os.path.exists(path):
                os.remove(path)

result = st.session_state.get("result")
if result:
    if not result["breakdown"]:
        st.warning(result.get("message", "We couldn't review this file."))
    else:
        p = result["percentage"]
        col = colour(p)
        title, blurb = verdict(p)
        prev = st.session_state.get("previous")
        delta = ""
        if prev is not None:
            d = p - prev
            if d > 0:
                delta = f'<br><span class="delta up">+{d} since your last review</span>'
            elif d < 0:
                delta = f'<br><span class="delta down">{d} since your last review</span>'
            else:
                delta = '<br><span class="delta same">No change since your last review</span>'

        st.markdown(
            f'<div class="pct" style="color:{col}">{p}<span>%</span></div>'
            f'<div class="track"><div class="fill" style="--w:{p}%;background:{col}"></div></div>'
            f'<div class="verdict"><b>{title}</b> <span>{blurb}</span>{delta}</div>',
            unsafe_allow_html=True,
        )

        st.markdown("### What to improve")
        for i, tip in enumerate(result["tips"]):
            cls = "tip top" if i < 2 else "tip"
            st.markdown(
                f'<div class="{cls}"><b>{html.escape(tip["problem"])}</b>'
                f'{html.escape(tip["fix"])}</div>',
                unsafe_allow_html=True,
            )

        with st.expander("How this score was calculated"):
            st.caption(
                f"Detected: {html.escape(result['field'])} ({html.escape(result['seniority'])}). "
                f"We found {result['statements_found']} statements describing your work: "
                f"{result['statements_quantified']} include numbers and "
                f"{result['statements_with_results']} show a result."
            )
            for name, value in result["breakdown"].items():
                earned, maximum = (float(x) for x in value.split(" / "))
                pct = earned / maximum * 100
                st.markdown(
                    f'<div class="brow"><span>{html.escape(name)}</span><span>{value}</span></div>'
                    f'<div class="btrack"><div class="bfill" '
                    f'style="width:{pct:.0f}%;background:{colour(pct)}"></div></div>',
                    unsafe_allow_html=True,
                )

st.markdown(
    '<div class="note">Your CV is analysed automatically and is not stored by this site. '
    'Its text is sent to an AI service (Google Gemini) to produce the review. '
    'The score is guidance, not a hiring prediction.</div>',
    unsafe_allow_html=True,
)