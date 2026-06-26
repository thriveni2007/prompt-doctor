"""
Prompt Doctor — Streamlit App
Two-panel layout: prompt editor + domain picker + level tracker (left);
examiner verdict + live output (right).
"""

import streamlit as st
import json

from levels import LEVELS
from examiner import grade_prompt

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Prompt Doctor",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------
if "current_level" not in st.session_state:
    st.session_state.current_level = 1
if "cleared_levels" not in st.session_state:
    st.session_state.cleared_levels = set()
if "prompt_history" not in st.session_state:
    st.session_state.prompt_history = {}  # level -> list of prompts tried
if "last_verdict" not in st.session_state:
    st.session_state.last_verdict = None
if "last_live_output" not in st.session_state:
    st.session_state.last_live_output = ""
if "student_prompt" not in st.session_state:
    st.session_state.student_prompt = ""
if "domain" not in st.session_state:
    st.session_state.domain = "Medical Scribe"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def get_level_data(level: int) -> dict:
    return LEVELS.get(level, LEVELS[1])


def is_level_unlocked(level: int) -> bool:
    if level == 1:
        return True
    return (level - 1) in st.session_state.cleared_levels


def submit_prompt():
    """Grade the current prompt and update session state."""
    level = st.session_state.current_level
    level_data = get_level_data(level)

    student_prompt = st.session_state.student_prompt.strip()
    if not student_prompt:
        st.warning("Write a prompt before submitting.")
        return

    with st.spinner("🧑‍⚕️ Examiner is grading your prompt..."):
        result = grade_prompt(
            student_prompt=student_prompt,
            level=level,
            principles=level_data["principles"],
            sample_input=level_data["sample_input"],
            level_task=level_data["task"],
            level_name=level_data["name"]
        )

    # Store result
    st.session_state.last_verdict = result["verdict"]
    st.session_state.last_live_output = result["live_output"]

    # Track history
    if level not in st.session_state.prompt_history:
        st.session_state.prompt_history[level] = []
    st.session_state.prompt_history[level].append({
        "prompt": student_prompt,
        "verdict": result["verdict"]
    })

    # Check pass
    if result["verdict"]["verdict"] == "pass":
        st.session_state.cleared_levels.add(level)
        if level < 5:
            st.session_state.current_level = level + 1
            st.session_state.student_prompt = ""
            st.session_state.last_verdict = None
            st.session_state.last_live_output = ""
            st.success(f"🎉 Level {level} passed! Moving to Level {level + 1}.")
            st.rerun()
        else:
            st.balloons()
            st.success("🏆 Congratulations! You've cleared all 5 levels!")


def reset_progress():
    """Reset all progress."""
    st.session_state.current_level = 1
    st.session_state.cleared_levels = set()
    st.session_state.prompt_history = {}
    st.session_state.last_verdict = None
    st.session_state.last_live_output = ""
    st.session_state.student_prompt = ""
    st.rerun()


# ---------------------------------------------------------------------------
# UI — Two-panel layout
# ---------------------------------------------------------------------------
# Title
col_title1, col_title2 = st.columns([3, 1])
with col_title1:
    st.title("🏥 Prompt Doctor")
    st.caption("The escalating prompt dojo — you write the prompts; an AI examiner decides when you've earned the next level.")
with col_title2:
    if st.button("🔄 Reset Progress", type="secondary", use_container_width=True):
        reset_progress()

# Two main panels
left_col, right_col = st.columns([1, 1.2], gap="large")

# ===================== LEFT PANEL =====================
with left_col:
    # --- Domain selector ---
    st.subheader("🎯 Domain")
    domain_options = [
        "Medical Scribe",
        "Legal",
        "Customer Support",
        "Finance",
        "Education",
        "Software Engineering",
        "Creative Writing",
        "Custom"
    ]
    selected_domain = st.selectbox(
        "Choose your domain:",
        domain_options,
        index=domain_options.index(st.session_state.domain)
        if st.session_state.domain in domain_options
        else 0,
        key="domain_selector"
    )
    st.session_state.domain = selected_domain

    st.divider()

    # --- Level tracker ---
    st.subheader("📊 Level Tracker")
    level_cols = st.columns(5)
    for i in range(1, 6):
        with level_cols[i - 1]:
            level_data = get_level_data(i)
            is_cleared = i in st.session_state.cleared_levels
            is_current = i == st.session_state.current_level
            is_unlocked = is_level_unlocked(i)

            if is_cleared:
                status = "✅"
                color = "green"
            elif is_current:
                status = "▶️"
                color = "#FFD700"
            elif is_unlocked:
                status = "🔓"
                color = "#87CEEB"
            else:
                status = "🔒"
                color = "#ccc"

            st.markdown(
                f"<div style='text-align:center; padding:5px; "
                f"background:{'#e8f5e9' if is_cleared else '#fff8e1' if is_current else '#f5f5f5'}; "
                f"border-radius:8px; border:2px solid {color};'>"
                f"<div style='font-size:24px;'>{status}</div>"
                f"<div style='font-size:11px; font-weight:bold;'>{level_data['name']}</div>"
                f"</div>",
                unsafe_allow_html=True
            )

    st.divider()

    # --- Current level info ---
    level = st.session_state.current_level
    level_data = get_level_data(level)

    st.subheader(f"Level {level}: {level_data['name']}")
    st.info(f"**Pass criteria:** {level_data['pass_criteria']}")

    with st.expander("📋 Task Details", expanded=True):
        st.markdown(f"**Task:**\n{level_data['task']}")
        st.markdown(f"**Sample Input:**")
        st.code(level_data["sample_input"], language="text")

    with st.expander("📏 Grading Principles", expanded=True):
        for p in level_data["principles"]:
            st.markdown(f"- {p}")

    st.divider()

    # --- Prompt editor ---
    st.subheader("✍️ Your Prompt")
    st.caption("Write the system prompt that will be evaluated by the examiner.")

    prompt = st.text_area(
        "Prompt:",
        value=st.session_state.student_prompt,
        height=250,
        placeholder="Write your prompt here... e.g.\n\nYou are a medical scribe AI. Extract the following from clinical notes...",
        key="prompt_editor",
        label_visibility="collapsed"
    )
    st.session_state.student_prompt = prompt

    # Submission
    submit_col1, submit_col2 = st.columns([2, 1])
    with submit_col1:
        submitted = st.button(
            "🧑‍⚕️ Submit for Grading",
            type="primary",
            use_container_width=True,
            disabled=not is_level_unlocked(level)
        )
    with submit_col2:
        st.button("Clear", use_container_width=True, on_click=lambda: setattr(
            st.session_state, "student_prompt", ""
        ))

    if submitted:
        submit_prompt()

    # History
    if level in st.session_state.prompt_history and st.session_state.prompt_history[level]:
        with st.expander("📜 Submission History", expanded=False):
            for idx, entry in enumerate(st.session_state.prompt_history[level]):
                v = entry["verdict"]["verdict"]
                icon = "✅" if v == "pass" else "❌"
                st.markdown(f"**Attempt {idx + 1}:** {icon} Verdict: **{v}**")
                st.code(entry["prompt"][:200] + ("..." if len(entry["prompt"]) > 200 else ""), language="text")

# ===================== RIGHT PANEL =====================
with right_col:
    st.subheader("🔍 Examiner Verdict")

    verdict = st.session_state.last_verdict
    live_output = st.session_state.last_live_output

    if verdict is None:
        st.info(
            "👋 No verdict yet. Write your prompt on the left and click "
            "**'Submit for Grading'** to get evaluated."
        )
        # Show placeholder layout
        st.divider()
        st.subheader("📤 Live Output")
        st.info("Live model output will appear here after submission.")

    else:
        # --- Principles breakdown ---
        st.markdown("### 📊 Principle-by-Principle Assessment")

        all_pass = True
        for p in verdict["principles"]:
            pname = p["name"].replace("_", " ").title()
            passed = p["pass"]
            weakness = p.get("weakness", "")
            question = p.get("question", "")

            if passed:
                st.markdown(
                    f"<div style='padding:8px 12px; margin:4px 0; "
                    f"background:#e8f5e9; border-left:4px solid #4CAF50; border-radius:4px;'>"
                    f"<span style='font-size:18px; color:#4CAF50;'>✅</span> "
                    f"<strong>{pname}</strong></div>",
                    unsafe_allow_html=True
                )
            else:
                all_pass = False
                st.markdown(
                    f"<div style='padding:8px 12px; margin:4px 0; "
                    f"background:#ffebee; border-left:4px solid #f44336; border-radius:4px;'>"
                    f"<span style='font-size:18px; color:#f44336;'>❌</span> "
                    f"<strong>{pname}</strong></div>",
                    unsafe_allow_html=True
                )
                if weakness:
                    st.markdown(
                        f"<div style='padding:4px 12px; margin:2px 0 2px 24px; "
                        f"color:#d32f2f; font-style:italic;'>"
                        f"💬 {weakness}</div>",
                        unsafe_allow_html=True
                    )
                if question:
                    st.markdown(
                        f"<div style='padding:4px 12px; margin:2px 0 2px 24px; "
                        f"color:#1565C0;'>"
                        f"❓ {question}</div>",
                        unsafe_allow_html=True
                    )

        # --- Overall verdict ---
        st.divider()
        if all_pass:
            st.success("### 🎉 PASS — All principles satisfied! Moving to next level...")
        else:
            st.warning("### 📝 REVISE — Some principles need work. Refine your prompt and resubmit.")

        # --- Live output ---
        st.divider()
        st.subheader("📤 Live Model Output")
        st.markdown(
            f"<div style='background:#1e1e1e; color:#d4d4d4; padding:12px; "
            f"border-radius:8px; font-family:monospace; font-size:13px; "
            f"max-height:400px; overflow-y:auto; white-space:pre-wrap;'>"
            f"{live_output}</div>",
            unsafe_allow_html=True
        )

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.divider()
st.caption(
    "Prompt Doctor  ·  GenAI & Agentic AI Engineering  ·  Day 2 Afternoon Lab  ·  "
    "Built with Streamlit + OpenRouter"
)