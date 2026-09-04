"""Chat UI helpers."""

import streamlit as st


def render_chat(df) -> None:
    """Render the QA assistant chat experience."""
    st.subheader("Ask the QA Assistant")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    question = st.chat_input("Ask a question about the test cases...")

    if question:
        with st.chat_message("user"):
            st.markdown(question)

        st.session_state.messages.append({"role": "user", "content": question})

        response = "The AI assistant is not available through the frontend API yet."
        with st.chat_message("assistant"):
            st.markdown(response)

        st.session_state.messages.append(
            {"role": "assistant", "content": response}
        )
        st.rerun()
