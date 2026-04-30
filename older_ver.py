import streamlit as st
import os, tempfile
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain.vectorstores import FAISS
from langchain.chains import RetrievalQA
import google.generativeai as genai

# 🔐 Set your Gemini API Key
os.environ["GOOGLE_API_KEY"] = "YOUR_GOOGLE_API_KEY_HERE"
genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

st.title("📄 PDF Q&A (Gemini-powered)")

pdf = st.file_uploader("Upload PDF", type="pdf")

if pdf:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(pdf.read())

    # Load + Split
    pages = PyPDFLoader(tmp.name).load()
    splits = CharacterTextSplitter(chunk_size=1000, chunk_overlap=200).split_documents(pages)

    # Embed + Store
    vectordb = FAISS.from_documents(splits, GoogleGenerativeAIEmbeddings(model="models/embedding-001"))

    # RAG Chain
    chain = RetrievalQA.from_chain_type(
        llm=ChatGoogleGenerativeAI(model="models/gemini-1.5-flash"),
        retriever=vectordb.as_retriever()
    )

    # Ask
    q = st.text_input("Ask a question:")
    if q:
        with st.spinner("Thinking..."):
            st.write("**Answer:**", chain.run(q))
