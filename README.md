# Ledger - PDF RAG Workspace

Ledger is a local PDF question-answering app. It has a React + Vite frontend, a FastAPI backend, and a Python RAG pipeline that chunks uploaded PDFs, embeds them, stores them in FAISS, and answers questions through an Ollama model.

## What It Does

- Upload a PDF from the browser
- Preview the uploaded PDF
- Split the PDF into retrieval chunks
- Create local embeddings with `all-MiniLM-L6-v2`
- Store chunks in a FAISS vector index
- Ask questions in a chat UI
- Retrieve relevant source chunks for each answer
- Show debug chunks when needed
- Change retrieval settings and click **Apply settings** to rebuild the current document index
- Use a sober blue neobrutalist interface with bold borders, hard shadows, and yellow highlights
- Detect when Ollama is offline and show a clean error instead of a traceback

## Project Structure

```text
.
├── RAG.py                 # FastAPI backend and Python RAG pipeline
├── semantic_chunking.py   # Small semantic chunking / embeddings experiment
├── requirements.txt       # Python dependencies
├── setup.md               # Detailed architecture and setup explanation
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── package-lock.json
│   └── src/
│       ├── main.jsx       # React app
│       └── styles.css     # Blue neobrutalist UI styling
└── Documents/             # Local PDFs, ignored by git
```

## Before You Start

You need these installed on your device:

- Python 3
- Node.js and npm
- Ollama

You can check Python and npm with:

```bash
python3 --version
npm --version
```

For Ollama, install it from the official Ollama app/site, then make sure this works:

```bash
ollama --version
```

## First-Time Setup

Do these steps once after cloning or downloading the project.

First, open a terminal inside the project folder:

```bash
cd "/Users/shwetakarandikar/Documents/cllz stuff/internship/cere labs"
```

Create the Python environment and install the backend packages:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Install the frontend packages:

```bash
npm install --prefix frontend
```

Download the local AI model used by the app:

```bash
ollama pull llama3
```

The app currently offers `llama3` and `phi3` in the model selector. If you want to use `phi3`, pull it too:

```bash
ollama pull phi3
```

## Run The App Every Time

You need three terminals open.

Terminal 1 starts Ollama:

```bash
ollama serve
```

Keep this terminal open.

Terminal 2 starts the Python backend:

```bash
cd "/Users/shwetakarandikar/Documents/cllz stuff/internship/cere labs"
source .venv/bin/activate
uvicorn RAG:app --reload --port 8000
```

Keep this terminal open too.

Terminal 3 starts the website:

```bash
cd "/Users/shwetakarandikar/Documents/cllz stuff/internship/cere labs"
npm run dev --prefix frontend
```

Now open this in your browser:

```text
http://localhost:5173
```

After the page opens:

1. Upload a PDF.
2. Wait for it to finish indexing.
3. Ask a question in the chat box.

If you change the model, chunk size, chunk overlap, or chunks to retrieve after uploading, click **Apply settings**. This rebuilds the current document index with the new control room values.

## Quick Health Check

If something feels broken, check the backend:

```bash
curl http://127.0.0.1:8000/api/health
```

If everything is okay, you should see that the API is `ok` and Ollama is connected.

You can also check whether a PDF is uploaded:

```bash
curl http://127.0.0.1:8000/api/state
```

If `hasDocument` is `true`, the upload worked.

To check the active retrieval settings, look at the `settings` object in the same response.

## Common Fixes

If chat says Ollama is not reachable, run:

```bash
ollama serve
```

If the model is missing, run:

```bash
ollama pull llama3
```

If upload works but the page looks stuck, refresh the browser and use:

```text
http://localhost:5173
```

If the backend is not responding, restart Terminal 2:

```bash
source .venv/bin/activate
uvicorn RAG:app --reload --port 8000
```

If the sliders changed but answers still feel like old settings, click **Apply settings**. Slider movement alone only changes the controls in the browser; applying rebuilds the backend retriever.

## Useful URLs

- Frontend: `http://localhost:5173`
- Backend API: `http://127.0.0.1:8000`
- API health check: `http://127.0.0.1:8000/api/health`
- API docs: `http://127.0.0.1:8000/docs`
- Apply current settings: `POST http://127.0.0.1:8000/api/apply-settings`

## Notes

- The frontend talks to the backend through `/api/*` endpoints.
- The backend talks to Ollama at `http://localhost:11434` by default.
- You can override Ollama's URL with `OLLAMA_BASE_URL`.
- `Indexed Chunks` means the total chunks created from the PDF.
- `Chunks to retrieve` means how many relevant chunks the app tries to retrieve for each question.
- The app can only retrieve as many chunks as exist in the index.
- `.env`, `.venv`, uploaded PDFs, generated frontend builds, and `node_modules` are ignored by git.
- Read [setup.md](setup.md) for the full end-to-end explanation.
