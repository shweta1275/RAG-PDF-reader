# Ledger - Retrieval-Based Document QA System

A Streamlit app for uploading a PDF and chatting with it using local retrieval and an Ollama model.

## Features

- Upload a PDF and index it locally
- Ask questions in a chat-style interface
- View retrieved source chunks
- Preview the uploaded PDF inside the app

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Make sure Ollama is installed and the model you want to use is available locally, for example:

```bash
ollama pull llama3
```

## Run

```bash
streamlit run pdf_final_version.py
```

## Notes

- `.env` is ignored and should not be pushed
- `.venv` is ignored and should not be pushed
- local PDFs inside `Documents/` are ignored
