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
        # Keep AI libraries out of the dashboard startup path. They are only
        # needed once the user actually submits a question.
        from langchain_core.messages import HumanMessage

        from evidenceiq.services.ai_service import ask_agent

        with st.chat_message("user"):
            st.markdown(question)

        st.session_state.messages.append({"role": "user", "content": question})

        history = []
        for message in st.session_state.messages:
            if message["role"] == "user":
                history.append(HumanMessage(content=message["content"]))
            elif message["role"] == "assistant":
                history.append(HumanMessage(content=message["content"]))

        response = ask_agent(question, df, history)
        with st.chat_message("assistant"):
            st.markdown(response)

        st.session_state.messages.append(
            {"role": "assistant", "content": response}
        )
        st.rerun()
