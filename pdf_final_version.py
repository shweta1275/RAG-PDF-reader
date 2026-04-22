import base64
import tempfile
import time

import streamlit as st
from langchain.chains import RetrievalQA
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.llms import Ollama
from langchain_community.vectorstores import FAISS


st.set_page_config(
    page_title="PDF Copilot",
    page_icon="📘",
    layout="wide",
    initial_sidebar_state="expanded",
)


CUSTOM_CSS = """
<style>
    .stApp {
        background: #f6f7f9;
        color: #16212c;
    }

    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    .hero-card {
        background: #ffffff;
        border: 1px solid rgba(22, 33, 44, 0.08);
        border-radius: 16px;
        padding: 1.5rem 1.7rem;
        box-shadow: 0 8px 24px rgba(22, 33, 44, 0.06);
        margin-bottom: 1rem;
    }

    .hero-badge {
        display: inline-block;
        padding: 0.35rem 0.8rem;
        border-radius: 999px;
        background: #16212c;
        color: #f8f5ef;
        font-size: 0.82rem;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        margin-bottom: 0.9rem;
    }

    .hero-title {
        font-size: 2.4rem;
        line-height: 1.05;
        font-weight: 800;
        margin-bottom: 0.4rem;
        color: #16212c;
    }

    .hero-copy {
        font-size: 1rem;
        color: #425466;
        margin-bottom: 0;
    }

    .glass-panel {
        background: #ffffff;
        border: 1px solid rgba(22, 33, 44, 0.08);
        border-radius: 16px;
        padding: 1rem 1.1rem;
        box-shadow: 0 8px 24px rgba(22, 33, 44, 0.06);
    }

    .stat-card {
        background: #ffffff;
        border: 1px solid rgba(22, 33, 44, 0.08);
        border-radius: 14px;
        padding: 1rem;
        box-shadow: 0 6px 18px rgba(22, 33, 44, 0.05);
    }

    .stat-label {
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #5f6f7d;
        margin-bottom: 0.35rem;
    }

    .stat-value {
        font-size: 1.55rem;
        font-weight: 800;
        color: #16212c;
    }

    div[data-testid="stChatMessage"] {
        background: #ffffff;
        border: 1px solid rgba(22, 33, 44, 0.08);
        border-radius: 16px;
        padding: 0.7rem 0.8rem;
        box-shadow: 0 6px 18px rgba(22, 33, 44, 0.05);
    }

    div[data-testid="stChatMessage"] *,
    div[data-testid="stChatMessage"] p,
    div[data-testid="stChatMessage"] span,
    div[data-testid="stChatMessage"] div,
    div[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] {
        color: #16212c !important;
    }

    div[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #16212c 0%, #243847 100%);
    }

    div[data-testid="stSidebar"] h1,
    div[data-testid="stSidebar"] h2,
    div[data-testid="stSidebar"] h3,
    div[data-testid="stSidebar"] label,
    div[data-testid="stSidebar"] p,
    div[data-testid="stSidebar"] .stCaption {
        color: #f7f3ed;
    }

    div[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
    div[data-testid="stSidebar"] [data-testid="stFileUploaderDropzoneInstructions"],
    div[data-testid="stSidebar"] [data-testid="stWidgetLabel"] {
        color: #f7f3ed;
    }

    .stButton > button,
    .stDownloadButton > button {
        width: 100%;
        background: #ffffff;
        color: #16212c !important;
        border: 1px solid rgba(22, 33, 44, 0.12);
        border-radius: 10px;
        box-shadow: 0 3px 10px rgba(22, 33, 44, 0.05);
        transition: all 0.2s ease;
    }

    .stButton > button *,
    .stDownloadButton > button * {
        color: #16212c !important;
    }

    .stButton > button:hover,
    .stDownloadButton > button:hover {
        background: #16212c;
        color: #f8f5ef !important;
        border-color: #16212c;
    }

    .stButton > button:hover *,
    .stDownloadButton > button:hover * {
        color: #f8f5ef !important;
    }

    .stButton > button:focus,
    .stDownloadButton > button:focus {
        color: #16212c;
        border-color: #118ab2;
        box-shadow: 0 0 0 0.2rem rgba(17, 138, 178, 0.18);
    }

    button[data-baseweb="tab"] {
        background: #ffffff;
        color: #16212c !important;
        border-radius: 10px 10px 0 0;
    }

    button[data-baseweb="tab"]:hover {
        color: #16212c !important;
        background: #eef2f6;
    }

    div[data-testid="stAlert"] *,
    div[data-testid="stInfo"] *,
    div[data-testid="stSuccess"] *,
    div[data-testid="stWarning"] * {
        color: #16212c !important;
    }

    [data-baseweb="select"] > div,
    [data-baseweb="select"] span,
    [data-baseweb="select"] input,
    .stSelectbox div[data-baseweb="select"] > div,
    .stTextInput input,
    .stNumberInput input,
    .stTextArea textarea,
    .stFileUploader label,
    .stFileUploader small {
        background: #ffffff;
        color: #16212c;
    }

    .stMultiSelect [data-baseweb="tag"] {
        background: #eef2f6;
        color: #16212c;
    }

    .stSlider [data-baseweb="slider"] * {
        color: #f7f3ed;
    }

    .stToggle label,
    .stCheckbox label,
    .stRadio label {
        color: #f7f3ed;
    }
</style>
"""


def init_session_state():
    defaults = {
        "messages": [],
        "vectordb": None,
        "chain": None,
        "doc_name": None,
        "pdf_bytes": None,
        "pages": [],
        "chunks": [],
        "last_uploaded_file": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


@st.cache_resource(show_spinner=False)
def load_embeddings():
    return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")


def reset_document_state():
    st.session_state.messages = []
    st.session_state.vectordb = None
    st.session_state.chain = None
    st.session_state.doc_name = None
    st.session_state.pdf_bytes = None
    st.session_state.pages = []
    st.session_state.chunks = []
    st.session_state.last_uploaded_file = None


def build_pdf_preview(pdf_bytes):
    encoded_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
    return f"""
        <iframe
            src="data:application/pdf;base64,{encoded_pdf}"
            width="100%"
            height="820"
            style="border:none; border-radius: 18px;"
        ></iframe>
    """


def build_qa_system(pdf_file, chunk_size, chunk_overlap, top_k, model_name):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(pdf_file.getvalue())
        temp_path = tmp.name

    pages = PyPDFLoader(temp_path).load()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    chunks = splitter.split_documents(pages)

    embeddings = load_embeddings()
    vectordb = FAISS.from_documents(chunks, embeddings)
    llm = Ollama(model=model_name)
    chain = RetrievalQA.from_chain_type(
        llm=llm,
        retriever=vectordb.as_retriever(search_kwargs={"k": top_k}),
        return_source_documents=True,
    )

    return pages, chunks, vectordb, chain


def render_stat_card(label, value):
    st.markdown(
        f"""
        <div class="stat-card">
            <div class="stat-label">{label}</div>
            <div class="stat-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


init_session_state()
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## Control Room")
    st.caption("Tune the experience before you chat with the document.")

    uploaded_pdf = st.file_uploader("  Upload a PDF", type="pdf")
    model_name = st.selectbox("Ollama model", ["llama3", "mistral", "phi3"], index=0)
    top_k = st.slider("Chunks to retrieve", min_value=2, max_value=8, value=4)
    chunk_size = st.slider("Chunk size", min_value=300, max_value=1500, value=900, step=100)
    chunk_overlap = st.slider("Chunk overlap", min_value=0, max_value=300, value=120, step=20)
    show_sources = st.toggle("Show source chunks", value=True)
    show_debug = st.toggle("Show debug workspace", value=False)

    if st.button("Reset workspace", use_container_width=True):
        reset_document_state()
        st.rerun()


st.markdown(
    """
    <div class="hero-card">
        <div class="hero-badge">Streamlit PDF Copilot</div>
        <div class="hero-title">Ask your document like it is sitting next to you.</div>
        <p class="hero-copy">
            Upload a PDF, inspect the source material, and chat with a local model through a cleaner,
            more expressive document workspace.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


if uploaded_pdf is not None:
    file_signature = (
        uploaded_pdf.name,
        uploaded_pdf.size,
        chunk_size,
        chunk_overlap,
        top_k,
        model_name,
    )
    if st.session_state.last_uploaded_file != file_signature:
        with st.spinner("Indexing your PDF and warming up the retriever..."):
            start_time = time.time()
            pages, chunks, vectordb, chain = build_qa_system(
                uploaded_pdf,
                chunk_size,
                chunk_overlap,
                top_k,
                model_name,
            )
            elapsed = time.time() - start_time

        st.session_state.pages = pages
        st.session_state.chunks = chunks
        st.session_state.vectordb = vectordb
        st.session_state.chain = chain
        st.session_state.doc_name = uploaded_pdf.name
        st.session_state.pdf_bytes = uploaded_pdf.getvalue()
        st.session_state.last_uploaded_file = file_signature
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": (
                    f"I've indexed **{uploaded_pdf.name}** and I'm ready. "
                    "Ask for a summary, definitions, comparisons, or citations."
                ),
                "sources": [],
            }
        ]
        st.toast(f"Indexed in {elapsed:.1f}s", icon="✨")


stats_col1, stats_col2, stats_col3 = st.columns(3)
with stats_col1:
    render_stat_card("Document", st.session_state.doc_name or "Waiting...")
with stats_col2:
    render_stat_card("Pages", len(st.session_state.pages))
with stats_col3:
    render_stat_card("Chunks", len(st.session_state.chunks))


left_col, right_col = st.columns([1.05, 1.25], gap="large")

with left_col:
    tabs = st.tabs(["Preview", "Quick Prompts", "Debug"])

    with tabs[0]:
        if st.session_state.pdf_bytes:
            st.components.v1.html(build_pdf_preview(st.session_state.pdf_bytes), height=840)
        else:
            st.info("Upload a PDF to unlock the live preview pane.")

    with tabs[1]:
        st.markdown("### Prompt ideas")
        prompts = [
            "Give me a 5-point summary of this PDF.",
            "What are the key concepts I should learn first?",
            "Pull out important definitions and explain them simply.",
            "What arguments or findings seem most important here?",
        ]
        for prompt in prompts:
            if st.button(prompt, use_container_width=True):
                st.session_state.prefill_prompt = prompt

    with tabs[2]:
        if show_debug and st.session_state.chunks:
            st.markdown("### Indexed chunks")
            for idx, chunk in enumerate(st.session_state.chunks[:10], start=1):
                page_num = chunk.metadata.get("page", "N/A")
                with st.expander(f"Chunk {idx} • Page {page_num}"):
                    st.write(chunk.page_content)
        elif show_debug:
            st.info("Debug data will show up here after a PDF is indexed.")
        else:
            st.caption("Enable `Show debug workspace` from the sidebar to inspect chunks.")

with right_col:
    st.markdown("### Chat With Your PDF")

    if not st.session_state.chain:
        st.info("Upload a PDF from the sidebar to start the chat experience.")
    else:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                if show_sources and message.get("sources"):
                    for idx, source in enumerate(message["sources"], start=1):
                        with st.expander(f"Source {idx} • Page {source['page']}"):
                            st.caption(source["label"])
                            st.write(source["content"])

        suggested_prompt = st.session_state.pop("prefill_prompt", "")
        user_query = st.chat_input(
            "Ask something about the uploaded PDF...",
            key="chat_box",
        )

        if suggested_prompt and not user_query:
            user_query = suggested_prompt

        if user_query:
            st.session_state.messages.append(
                {"role": "user", "content": user_query, "sources": []}
            )
            with st.chat_message("user"):
                st.markdown(user_query)

            with st.chat_message("assistant"):
                with st.spinner("Reading the document and composing an answer..."):
                    response = st.session_state.chain({"query": user_query})

                answer = response["result"]
                source_documents = response.get("source_documents", [])
                formatted_sources = []
                for doc in source_documents:
                    page_num = doc.metadata.get("page", "N/A")
                    formatted_sources.append(
                        {
                            "page": page_num,
                            "label": f"Retrieved from page {page_num}",
                            "content": doc.page_content,
                        }
                    )

                st.markdown(answer)
                if show_sources and formatted_sources:
                    for idx, source in enumerate(formatted_sources, start=1):
                        with st.expander(f"Source {idx} • Page {source['page']}"):
                            st.caption(source["label"])
                            st.write(source["content"])

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": answer,
                    "sources": formatted_sources,
                }
            )
