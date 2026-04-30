# Ledger Setup And Architecture

This document explains the project end to end: what we are building, how the frontend connects to the backend, how FastAPI is used, how the Python RAG pipeline works, and where chunking, embeddings, FAISS, and Ollama fit.

## 1. What We Are Building

Ledger is a local PDF RAG application.

RAG means retrieval-augmented generation. Instead of sending an entire PDF to the language model every time, the app first breaks the PDF into smaller text chunks, stores those chunks in a searchable vector index, retrieves the chunks most relevant to the user's question, and sends only that relevant context to the model.

The app has three main layers:

```text
React + Vite frontend
        |
        | HTTP requests with fetch()
        v
FastAPI backend in RAG.py
        |
        | LangChain, PyPDF, HuggingFace embeddings, FAISS
        v
Local RAG pipeline + Ollama model
```

The frontend is responsible for the user experience. The backend is responsible for file handling, PDF parsing, chunking, vector search, and model calls.

## 2. Main Files

```text
RAG.py
```

This is the Python backend. It creates the FastAPI app, defines API routes, stores the current uploaded document in memory, builds the RAG chain, and sends chat questions to Ollama.

```text
frontend/src/main.jsx
```

This is the main React application. It renders the sidebar controls, upload area, Apply settings button, PDF preview, quick prompts, debug chunks, chat messages, and source chunks.

```text
frontend/src/styles.css
```

This contains the blue neobrutalist UI styling. The design uses a focused blue palette, thick borders, hard shadows, white document panels, and small yellow highlights for emphasis.

```text
semantic_chunking.py
```

This is a separate experiment file. It demonstrates sentence splitting and optional Google embeddings. It is not currently wired into the main FastAPI app, but it is useful for understanding chunking and embedding ideas.

```text
requirements.txt
```

This lists the Python dependencies for the backend and RAG pipeline.

```text
frontend/package.json
```

This lists the JavaScript dependencies and frontend scripts.

## 3. Frontend Layer

The frontend is built with React and Vite.

React gives us reusable UI components and state management. Vite gives us a fast development server, hot reload, and production builds.

The app starts at:

```text
frontend/src/main.jsx
```

Important frontend state:

```js
state
```

Stores document metadata returned by the backend:

- document name
- page count
- indexed chunk count
- whether a PDF is uploaded
- indexing time

```js
settings
```

Stores the current RAG controls:

- selected Ollama model
- chunks to retrieve
- chunk size
- chunk overlap

These values are editable in the sidebar. After a PDF is uploaded, changing them does not automatically rebuild the backend index. The user clicks **Apply settings** to send the staged values to the backend and rebuild the current document index.

```js
messages
```

Stores the chat history shown in the browser.

```js
health
```

Stores Ollama connection status from the backend health endpoint.

## 4. Frontend Features

The React UI has these main parts:

```text
Sidebar
```

The sidebar contains upload, model selection, chunk controls, toggles, Ollama status, Apply settings, and reset.

```text
Stats
```

The stats row shows document name, page count, and indexed chunk count.

Important distinction:

- `Indexed Chunks` is the total number of chunks created from the PDF.
- `Chunks to retrieve` is the maximum number of relevant chunks the retriever should fetch for each question.
- If a PDF only has 4 indexed chunks, setting chunks to retrieve to 7 cannot return 7 chunks. It can only return what exists.

```text
Preview tab
```

The preview tab loads the PDF from:

```text
GET /api/pdf
```

The backend returns the original PDF bytes, and the browser displays them in an iframe.

```text
Prompts tab
```

The prompts tab has quick prompt buttons. Clicking one sends it to the same chat function as a normal typed question.

```text
Debug tab
```

The debug tab calls:

```text
GET /api/chunks
```

It shows the indexed chunks so you can inspect how the PDF was split.

```text
Chat panel
```

The chat panel sends questions to:

```text
POST /api/chat
```

The backend returns an answer and source chunks.

```text
Apply settings button
```

The Apply settings button sends the current sidebar settings to:

```text
POST /api/apply-settings
```

This reuses the already uploaded PDF bytes and rebuilds the pages, chunks, FAISS index, retriever, and RetrievalQA chain with the new settings.

## 5. How The Frontend Talks To The Backend

The frontend uses the browser's `fetch()` API.

The base API URL is:

```js
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
```

This means:

- during normal local development, the frontend talks to `http://localhost:8000`
- later, you can set `VITE_API_URL` if the backend runs somewhere else

The helper function in `main.jsx` is:

```js
async function api(path, options = {}) {
  const response = await fetch(`${API_URL}${path}`, options);
  ...
}
```

Every frontend API call goes through this helper. If the backend returns an error, the helper turns that into a JavaScript `Error`, and the UI shows the message cleanly.

## 6. Backend Layer

The backend is built with FastAPI.

FastAPI lets us define HTTP endpoints in Python. The frontend can call those endpoints from the browser.

The app is created in `RAG.py`:

```python
app = FastAPI(title="Ledger PDF QA API")
```

The backend also enables CORS:

```python
app.add_middleware(CORSMiddleware, ...)
```

CORS is needed because the frontend runs on `localhost:5173` and the backend runs on `localhost:8000`. Those are different origins, so the browser needs permission to let them talk.

## 7. Backend State

The current app stores one uploaded PDF workspace in memory:

```python
workspace = {
    "doc_name": None,
    "pdf_bytes": None,
    "pages": [],
    "chunks": [],
    "chain": None,
    "settings": None,
    "last_indexed_seconds": None,
}
```

This is simple and useful for local development.

Important limitation: this state is not persistent. If the backend restarts, the uploaded PDF and vector index disappear. For a production app, you would likely store uploaded files and vector indexes on disk or in a database.

## 8. Backend API Routes

```text
GET /api/health
```

Checks that the API is running and checks whether Ollama is reachable.

```text
GET /api/state
```

Returns the current document state: document name, page count, chunk count, settings, and whether a document exists.

```text
POST /api/upload
```

Accepts a PDF and indexing settings from the frontend. It parses the PDF, chunks it, embeds it, builds a FAISS index, and creates a LangChain RetrievalQA chain.

```text
POST /api/apply-settings
```

Rebuilds the current uploaded PDF using the latest control room settings. This is used when the user changes model, chunks to retrieve, chunk size, or chunk overlap after upload.

```text
GET /api/pdf
```

Returns the uploaded PDF bytes so the frontend can preview the document.

```text
GET /api/chunks
```

Returns the first indexed chunks for debugging.

```text
POST /api/chat
```

Accepts a user question, runs retrieval, calls Ollama through LangChain, and returns an answer with source chunks.

```text
POST /api/reset
```

Clears the current in-memory workspace.

## 9. PDF Upload Flow

When you upload a PDF in the browser:

1. React reads the selected file from the upload input.
2. React creates a `FormData` object.
3. React adds the PDF and current settings to that form:

```js
formData.append('file', file);
formData.append('model_name', settings.modelName);
formData.append('top_k', settings.topK);
formData.append('chunk_size', settings.chunkSize);
formData.append('chunk_overlap', settings.chunkOverlap);
```

4. React sends it to:

```text
POST /api/upload
```

5. FastAPI receives it as:

```python
file: UploadFile = File(...)
model_name: str = Form("llama3")
top_k: int = Form(4)
chunk_size: int = Form(900)
chunk_overlap: int = Form(120)
```

6. The backend reads the PDF bytes.
7. The backend builds the RAG system.
8. The backend updates `workspace`.
9. React receives document stats and shows the app as ready.

## 10. Apply Settings Flow

The control room settings are split into two stages:

```text
Browser settings
```

These are the slider/select values visible in the sidebar.

```text
Backend settings
```

These are the values that were actually used to build the current FAISS index and retriever.

When the user uploads a PDF, the current browser settings are sent with the upload and immediately used for indexing.

When the user changes the controls after upload, the browser settings change, but the backend index is not rebuilt automatically. This avoids expensive re-indexing on every tiny slider movement.

To apply the new settings, the user clicks **Apply settings**.

The frontend sends:

```text
POST /api/apply-settings
```

with JSON:

```json
{
  "modelName": "llama3",
  "topK": 7,
  "chunkSize": 700,
  "chunkOverlap": 100
}
```

FastAPI validates that with:

```python
class SettingsRequest(BaseModel):
    modelName: str = "llama3"
    topK: int = 4
    chunkSize: int = 900
    chunkOverlap: int = 120
```

Then the backend:

1. Checks that a PDF has already been uploaded.
2. Reuses `workspace["pdf_bytes"]`.
3. Runs `build_qa_system(...)` again with the new settings.
4. Replaces the old pages, chunks, chain, and settings in `workspace`.
5. Returns the new document state.

The frontend then updates the stats and shows a confirmation message in chat:

```text
Applied the control room settings and rebuilt the document index with 7 chunks retrieved per question.
```

## 11. Python RAG Pipeline

The core RAG setup happens inside:

```python
build_qa_system(...)
```

The pipeline has several steps.

## 12. Step 1: Save The Uploaded PDF Temporarily

LangChain's `PyPDFLoader` expects a file path, not raw bytes. The backend receives bytes from the browser, so it writes them to a temporary PDF file:

```python
with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
    tmp.write(pdf_bytes)
    temp_path = tmp.name
```

After loading, the temp file is deleted:

```python
os.unlink(temp_path)
```

## 13. Step 2: Load PDF Pages

The backend uses:

```python
PyPDFLoader(temp_path).load()
```

This returns LangChain `Document` objects. Each page has:

- `page_content`: extracted text
- `metadata`: information such as page number

## 14. Step 3: Chunk The Text

The backend uses:

```python
RecursiveCharacterTextSplitter(
    chunk_size=chunk_size,
    chunk_overlap=chunk_overlap,
)
```

Chunking means splitting long text into smaller pieces.

Why chunking matters:

- LLMs have context limits
- retrieval works better with smaller searchable units
- answers can cite the specific chunks that were used

`chunk_size` controls the approximate maximum chunk length.

`chunk_overlap` keeps some repeated text between neighboring chunks. This helps avoid losing meaning at chunk boundaries.

Example:

```text
Chunk 1: Introduction ... retrieval augmented generation is useful because ...
Chunk 2: generation is useful because ... it combines search with language models ...
```

The overlap means Chunk 2 still has enough context from the end of Chunk 1.

## 15. Step 4: Create Embeddings

The app uses:

```python
HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
```

An embedding is a list of numbers that represents the meaning of text. Similar texts produce similar vectors.

For example:

```text
"What is retrieval?"
"Explain RAG search."
```

These should be close in vector space because they are semantically related.

The embedding model runs locally through the Python environment. This is separate from Ollama.

## 16. Step 5: Store Chunks In FAISS

The app uses:

```python
FAISS.from_documents(chunks, load_embeddings())
```

FAISS is a vector database/index. It stores chunk embeddings and lets us search for the chunks most similar to a question.

When the user asks a question, the question is embedded too. FAISS compares that question embedding against the chunk embeddings and returns the best matches.

## 17. Step 6: Create The Retriever

The vector database becomes a retriever:

```python
vectordb.as_retriever(search_kwargs={"k": top_k})
```

`top_k` means how many chunks to retrieve for each question.

If `top_k = 4`, the backend retrieves the 4 most relevant chunks and sends them to the language model as context.

If the index contains fewer than `top_k` chunks, FAISS can only return the chunks that exist. For example, `top_k = 7` does not create 7 chunks; chunk creation is controlled by `chunk_size` and `chunk_overlap`.

## 18. Step 7: Connect To Ollama

The app uses:

```python
Ollama(model=model_name, base_url=OLLAMA_BASE_URL)
```

By default:

```python
OLLAMA_BASE_URL = "http://localhost:11434"
```

Ollama must be running separately:

```bash
ollama serve
```

The selected model must also be available:

```bash
ollama pull llama3
```

The UI currently exposes two model choices: `llama3` and `phi3`. Pull `phi3` as well if you want to select it:

```bash
ollama pull phi3
```

If Ollama is not running, the backend catches the connection problem and returns a friendly error.

## 19. Step 8: Build The RetrievalQA Chain

The app uses LangChain:

```python
RetrievalQA.from_chain_type(
    llm=llm,
    retriever=vectordb.as_retriever(search_kwargs={"k": top_k}),
    return_source_documents=True,
)
```

This chain handles the question-answering flow:

1. Receive the user's question.
2. Retrieve relevant chunks from FAISS.
3. Put those chunks into a prompt.
4. Send the prompt to Ollama.
5. Return the answer.
6. Return source documents too.

## 20. Chat Flow

When the user asks a question:

1. React sends:

```text
POST /api/chat
```

with JSON:

```json
{
  "query": "Summarize this PDF"
}
```

2. FastAPI validates the request with Pydantic:

```python
class ChatRequest(BaseModel):
    query: str
```

3. The backend checks that a PDF has already been uploaded.
4. The backend runs:

```python
workspace["chain"].invoke({"query": query})
```

5. LangChain retrieves chunks and calls Ollama.
6. The backend formats source documents.
7. React receives:

```json
{
  "answer": "...",
  "sources": [
    {
      "page": 1,
      "label": "Retrieved from page 1",
      "content": "..."
    }
  ]
}
```

8. React renders the answer and expandable source chunks.

## 21. Why FastAPI Is Needed

React runs in the browser. Browser JavaScript cannot safely run the Python RAG pipeline directly.

FastAPI acts as the bridge:

```text
Browser UI
  cannot directly use PyPDFLoader, FAISS, LangChain, or local Python models

FastAPI backend
  can use Python libraries, read uploaded files, build indexes, and call Ollama
```

The frontend sends normal HTTP requests. The backend performs the Python work and returns JSON.

## 22. Why We Moved Away From Streamlit

Streamlit is great for fast prototypes, but the UI was becoming hard to control:

- the sidebar layout was cramped
- styling native Streamlit widgets is limited
- tracebacks appeared directly in the UI
- app state and backend logic were mixed in one script

The new structure separates responsibilities:

```text
React = UI
FastAPI = API layer
Python/LangChain = document intelligence
Ollama = local LLM
```

This makes the app easier to design, debug, and extend.

## 23. UI Design Direction

The current frontend uses a restrained neobrutalist visual style.

The design choices are:

- blue-centered palette
- navy text and borders
- pale blue page background
- white and very light blue panels
- yellow only for small highlights
- hard offset shadows instead of soft glass shadows
- thick borders around controls and panels

The goal is to keep the app visually distinct without making it loud or hard to read.

## 24. Error Handling

The original issue was:

```text
requests.exceptions.ConnectionError: HTTPConnectionPool(host='localhost', port=11434)
```

That means the Python code tried to call Ollama at `localhost:11434`, but no Ollama server was accepting connections.

Now the backend handles this in two places:

```text
GET /api/health
```

This checks whether Ollama is reachable.

```text
POST /api/chat
```

This catches connection errors and returns:

```text
Ollama is not running on localhost:11434. Start it with `ollama serve`, then run `ollama pull llama3` if needed.
```

The frontend displays that message inside the chat instead of showing a Python traceback.

## 25. Running The Project

Install Python dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Install frontend dependencies:

```bash
npm install --prefix frontend
```

Start Ollama:

```bash
ollama serve
```

Pull the model:

```bash
ollama pull llama3
```

Optional second model:

```bash
ollama pull phi3
```

Start the backend:

```bash
source .venv/bin/activate
uvicorn RAG:app --reload --port 8000
```

Start the frontend:

```bash
npm run dev --prefix frontend
```

Open:

```text
http://localhost:5173
```

## 26. API Testing Commands

Health check:

```bash
curl http://127.0.0.1:8000/api/health
```

Upload a test PDF:

```bash
curl -X POST http://127.0.0.1:8000/api/upload \
  -F "file=@Documents/testing.pdf;type=application/pdf" \
  -F model_name=llama3 \
  -F top_k=4 \
  -F chunk_size=900 \
  -F chunk_overlap=120
```

Ask a question:

```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"query":"Summarize this PDF"}'
```

Apply new settings to the already uploaded PDF:

```bash
curl -X POST http://127.0.0.1:8000/api/apply-settings \
  -H "Content-Type: application/json" \
  -d '{"modelName":"llama3","topK":7,"chunkSize":700,"chunkOverlap":100}'
```

Reset:

```bash
curl -X POST http://127.0.0.1:8000/api/reset
```

## 27. Current Limitations

- The backend stores only one uploaded PDF at a time.
- Workspace state is in memory and resets when the backend restarts.
- There is no user authentication.
- Uploaded PDFs are not persisted.
- The FAISS index is rebuilt on every upload and every Apply settings action.
- The current semantic chunking experiment is not yet connected to the main backend.

## 28. Good Next Improvements

- Add persistent document storage.
- Save and reload FAISS indexes.
- Support multiple uploaded PDFs.
- Add streaming responses from Ollama.
- Move RAG logic from `RAG.py` into smaller modules.
- Connect a true semantic chunker if we want smarter splitting than character-based chunking.
- Add tests for upload, reset, health, and chat error handling.
