"""Streamlit chat UI for the FarmerScheme chatbot - calls the FastAPI backend's
/chat endpoint (see backend/main.py) and renders the conversation.

Usage (from project root, with venv active, backend already running):
    streamlit run frontend\\app.py
"""

import os

import requests
import streamlit as st

DEFAULT_BACKEND_URL = (
    os.environ.get("BACKEND_URL", "http://127.0.0.1:8000").strip().rstrip("/")
)


def _dedupe_urls(urls):
    seen = set()
    unique = []
    for url in urls:
        if url and url not in seen:
            seen.add(url)
            unique.append(url)
    return unique


BACKEND_URLS = _dedupe_urls(
    [
        DEFAULT_BACKEND_URL,
        "http://127.0.0.1:8010",
        "http://127.0.0.1:8000",
    ]
)


def get_backend_url():
    for base_url in BACKEND_URLS:
        try:
            response = requests.get(f"{base_url}/health", timeout=2)
            if response.ok:
                return base_url
        except requests.RequestException:
            continue
    return DEFAULT_BACKEND_URL


# Minimal English-only UI for the production deployment.
UI_STRINGS = {
    "en": {
        "title": "FarmerScheme chatbot",
        "caption": "Ask about Tamil Nadu government farmer welfare schemes.",
        "new_chat": "New Chat",
        "chat_history": "Chat History",
        "no_messages": "No messages yet.",
        "input_placeholder": "Type your question",
        "thinking": "Thinking...",
        "backend_error": "Could not reach the backend at {url}. Is it running? ({error})",
    }
}

st.set_page_config(page_title="FarmerScheme chatbot")

st.markdown(
    """
    <style>
    /* Tighter line spacing inside chat bubbles */
    [data-testid="stChatMessageContent"] p {
        margin-bottom: 0.3rem;
        margin-top: 0.3rem;
        line-height: 1.3;
    }
    /* Monospace font for any link, e.g. source links */
    a {
        font-family: Consolas, "Courier New", monospace;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "chat_sessions" not in st.session_state:
    st.session_state.chat_sessions = (
        []
    )  # List of (session_id, first_query, full_messages) tuples
if "loaded_from_history" not in st.session_state:
    st.session_state.loaded_from_history = False
if "current_session_index" not in st.session_state:
    st.session_state.current_session_index = (
        None  # Track which history entry is being edited
    )

# English-only hardcoded for this deployment
current_code = "en"
ui = UI_STRINGS.get(current_code, UI_STRINGS["en"])

st.title(ui["title"])
st.caption(ui["caption"])

with st.sidebar:
    if st.button(ui["new_chat"]):
        # Save current chat to history before starting new one
        if st.session_state.messages and st.session_state.messages[0]["role"] == "user":
            first_query = st.session_state.messages[0]["content"][:60]
            # If editing an existing history entry, update it; otherwise add new
            if st.session_state.current_session_index is not None:
                # Update existing entry
                session_id, _, _ = st.session_state.chat_sessions[
                    st.session_state.current_session_index
                ]
                st.session_state.chat_sessions[
                    st.session_state.current_session_index
                ] = (
                    session_id,
                    first_query,
                    st.session_state.messages.copy(),
                )
            else:
                # Add new entry
                st.session_state.chat_sessions.insert(
                    0,
                    (
                        st.session_state.session_id,
                        first_query,
                        st.session_state.messages.copy(),
                    ),
                )
                # Keep only last 5 sessions
                st.session_state.chat_sessions = st.session_state.chat_sessions[:5]

        # Start new chat
        st.session_state.session_id = None
        st.session_state.messages = []
        st.session_state.loaded_from_history = False
        st.session_state.current_session_index = None
        st.rerun()

    st.divider()
    st.subheader(ui["chat_history"])

    # Display current chat (only first message if it exists)
    if st.session_state.messages and st.session_state.messages[0]["role"] == "user":
        current_preview = (
            st.session_state.messages[0]["content"].replace("\n", " ").strip()[:60]
        )
        st.caption(f"📌 {current_preview}")

    st.caption("---")

    # Display past sessions (clickable)
    if not st.session_state.chat_sessions:
        st.caption(ui["no_messages"])
    else:
        for idx, (session_id, first_query, full_messages) in enumerate(
            st.session_state.chat_sessions
        ):
            if st.button(first_query, key=f"session_{idx}"):
                # Load this session
                st.session_state.session_id = session_id
                st.session_state.messages = full_messages.copy()
                st.session_state.loaded_from_history = True
                st.session_state.current_session_index = (
                    idx  # Track which entry is being edited
                )
                st.rerun()


def render_reply(content):
    st.write(content)


# Display loaded message (if loaded from history)
if st.session_state.loaded_from_history:
    st.info("📋 Loaded from chat history. Continue your chat below.")
    st.session_state.loaded_from_history = False  # Show once

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            render_reply(message["content"])
        else:
            st.write(message["content"])

question = st.chat_input(ui["input_placeholder"])

if question:
    st.session_state.messages.append({"role": "user", "content": question})

    # Update chat history after adding user message
    if st.session_state.messages:
        first_query = st.session_state.messages[0]["content"][:60]
        if st.session_state.current_session_index is not None:
            # Update existing history entry
            session_id, _, _ = st.session_state.chat_sessions[
                st.session_state.current_session_index
            ]
            st.session_state.chat_sessions[st.session_state.current_session_index] = (
                session_id,
                first_query,
                st.session_state.messages.copy(),
            )
        else:
            # Create new history entry if none exists
            st.session_state.chat_sessions.insert(
                0,
                (
                    st.session_state.session_id,
                    first_query,
                    st.session_state.messages.copy(),
                ),
            )
            st.session_state.current_session_index = 0
            st.session_state.chat_sessions = st.session_state.chat_sessions[:5]

    with st.chat_message("user"):
        st.write(question)

    with st.chat_message("assistant"):
        with st.spinner(ui["thinking"]):
            backend_url = st.session_state.get("backend_url") or get_backend_url()
            st.session_state.backend_url = backend_url
            try:
                response = requests.post(
                    f"{backend_url}/chat",
                    json={
                        "message": question,
                        "session_id": st.session_state.session_id,
                        "language": current_code,
                    },
                    timeout=60,
                )
                response.raise_for_status()
                data = response.json()
            except requests.RequestException as error:
                st.error(ui["backend_error"].format(url=backend_url, error=error))
                st.stop()

        if data.get("answer") and data["answer"].startswith(
            ("OpenAI", "The chatbot", "The AI service")
        ):
            st.error(data["answer"])
        else:
            st.session_state.session_id = data.get("session_id")
            render_reply(data.get("answer", "No response from backend."))

    st.session_state.messages.append(
        {"role": "assistant", "content": data["answer"], "sources": data["sources"]}
    )

    # Update chat history after adding assistant message
    if st.session_state.messages:
        first_query = st.session_state.messages[0]["content"][:60]
        if st.session_state.current_session_index is not None:
            # Update existing history entry
            session_id, _, _ = st.session_state.chat_sessions[
                st.session_state.current_session_index
            ]
            st.session_state.chat_sessions[st.session_state.current_session_index] = (
                session_id,
                first_query,
                st.session_state.messages.copy(),
            )
