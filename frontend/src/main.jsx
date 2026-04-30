import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  ArrowUp,
  ArrowLeft,
  Bot,
  FileText,
  Loader2,
  RefreshCw,
  Sparkles,
  Upload,
  User,
} from 'lucide-react';
import FadeContent from './FadeContent';
import SplitText from './SplitText';
import ScrollVelocity from './ScrollVelocity';
import './styles.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const prompts = [
  'Give me a 5-point summary of this PDF.',
  'What are the key concepts I should learn first?',
  'Pull out important definitions and explain them simply.',
  'What arguments or findings seem most important here?',
];

function App() {
  const [view, setView] = useState('landing');
  const viewRef = useRef('landing');

  // Handle browser back/forward navigation
  useEffect(() => {
    const handlePopState = () => {
      const newView = window.history.state?.view || 'landing';
      setView(newView);
      viewRef.current = newView;
    };

    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  // Navigation function that updates both state and history
  const navigate = (newView) => {
    setView(newView);
    viewRef.current = newView;
    window.history.pushState({ view: newView }, '', `#${newView}`);
  };

  // Initialize history state on mount
  useEffect(() => {
    if (!window.history.state) {
      window.history.replaceState({ view: 'landing' }, '', '#landing');
    }
  }, []);

  const [state, setState] = useState({
    docName: null,
    pages: 0,
    chunks: 0,
    hasDocument: false,
  });
  const [health, setHealth] = useState(null);
  const [messages, setMessages] = useState([]);
  const [chunks, setChunks] = useState([]);
  const [activeTab, setActiveTab] = useState('preview');
  const [settings, setSettings] = useState({
    modelName: 'llama3',
    topK: 4,
    chunkSize: 900,
    chunkOverlap: 120,
  });
  const [showSources, setShowSources] = useState(true);
  const [showDebug, setShowDebug] = useState(false);
  const [query, setQuery] = useState('');
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const fileInputRef = useRef(null);

  const pdfUrl = useMemo(() => {
    return state.hasDocument ? `${API_URL}/api/pdf?cache=${state.docName}` : '';
  }, [state.hasDocument, state.docName]);

  useEffect(() => {
    refreshState();
    refreshHealth();
  }, []);

  async function api(path, options = {}) {
    const response = await fetch(`${API_URL}${path}`, options);
    const contentType = response.headers.get('content-type') || '';
    const data = contentType.includes('application/json')
      ? await response.json()
      : await response.text();
    if (!response.ok) {
      throw new Error(data.detail || data.message || 'Something went wrong.');
    }
    return data;
  }

  async function refreshState() {
    const nextState = await api('/api/state');
    setState(nextState);
    if (nextState.settings) {
      setSettings({
        modelName: nextState.settings.modelName,
        topK: nextState.settings.topK,
        chunkSize: nextState.settings.chunkSize,
        chunkOverlap: nextState.settings.chunkOverlap,
      });
    }
  }

  async function refreshHealth() {
    const data = await api('/api/health');
    setHealth(data.ollama);
  }

  async function loadChunks() {
    const data = await api('/api/chunks');
    setChunks(data.chunks);
  }

  async function handleUpload(event) {
    const file = event.target.files?.[0];
    if (!file) return;

    setBusy(true);
    setNotice('Indexing your PDF...');
    const formData = new FormData();
    formData.append('file', file);
    formData.append('model_name', settings.modelName);
    formData.append('top_k', settings.topK);
    formData.append('chunk_size', settings.chunkSize);
    formData.append('chunk_overlap', settings.chunkOverlap);

    try {
      const data = await api('/api/upload', {
        method: 'POST',
        body: formData,
      });
      setState(data);
      setMessages([{ role: 'assistant', content: data.message, sources: [] }]);
      setNotice(`Indexed in ${data.indexedSeconds}s`);
      if (showDebug) loadChunks();
    } catch (error) {
      setNotice(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function ask(text = query) {
    const clean = text.trim();
    if (!clean || busy) return;

    setQuery('');
    setBusy(true);
    setNotice('');
    setMessages((current) => [
      ...current,
      { role: 'user', content: clean, sources: [] },
      { role: 'assistant', content: 'Reading the document...', sources: [], pending: true },
    ]);

    try {
      const data = await api('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: clean }),
      });
      setMessages((current) => [
        ...current.filter((message) => !message.pending),
        { role: 'assistant', content: data.answer, sources: data.sources || [] },
      ]);
    } catch (error) {
      setMessages((current) => [
        ...current.filter((message) => !message.pending),
        { role: 'assistant', content: error.message, sources: [], error: true },
      ]);
    } finally {
      setBusy(false);
      refreshHealth();
    }
  }

  async function resetWorkspace() {
    setBusy(true);
    try {
      const data = await api('/api/reset', { method: 'POST' });
      setState(data);
      setMessages([]);
      setChunks([]);
      setNotice('');
      if (fileInputRef.current) fileInputRef.current.value = '';
    } finally {
      setBusy(false);
    }
  }

  async function applySettings() {
    if (!state.hasDocument) {
      setNotice('Upload a PDF before applying settings.');
      return;
    }

    setBusy(true);
    setNotice('Applying control room settings...');
    try {
      const data = await api('/api/apply-settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings),
      });
      setState(data);
      setMessages([
        {
          role: 'assistant',
          content: data.message,
          sources: [],
        },
      ]);
      setNotice(`Applied in ${data.indexedSeconds}s`);
      if (showDebug) loadChunks();
    } catch (error) {
      setNotice(error.message);
    } finally {
      setBusy(false);
    }
  }

  function updateSetting(key, value) {
    setSettings((current) => ({ ...current, [key]: value }));
  }


  if (view === 'landing') {
    return <LandingPage 
      onOpenBasic={() => navigate('basic')} 
      onOpenSemrag={() => navigate('semrag')} 
      onOpenVectorlessRah={() => navigate('vectorlessrah')} 
    />;
  }

  if (view === 'semrag') {
    return <SemragPage onBack={() => navigate('landing')} />;
  }

  if (view === 'vectorlessrah') {
    return <VectorlessRahPage onBack={() => navigate('landing')} />;
  }

  return (
    <main className="app">
      <aside className="sidebar">
        <div>
          <button className="home-link" type="button" onClick={() => navigate('landing')}>
            <ArrowLeft size={16} />
            Home
          </button>
          <p className="eyebrow">Control Room</p>
          <h1>Ledger</h1>
          <p className="muted">Tune retrieval, upload a PDF, and chat with local context.</p>
        </div>

        <label className="upload-zone">
          <span className="upload-icon"><Upload size={20} /></span>
          <span>
            <strong>{state.docName || 'Upload a PDF'}</strong>
            <small>{state.docName ? 'Ready to index another document' : 'Drop in a text-based PDF'}</small>
          </span>
          <input ref={fileInputRef} type="file" accept="application/pdf" onChange={handleUpload} />
        </label>

        <label className="field">
          <span>Ollama model</span>
          <select
            value={settings.modelName}
            onChange={(event) => updateSetting('modelName', event.target.value)}
          >
            <option value="llama3">llama3</option>
            <option value="phi3">phi3</option>
          </select>
        </label>

        <Slider label="Chunks to retrieve" min={2} max={8} value={settings.topK} onChange={(value) => updateSetting('topK', value)} />
        <Slider label="Chunk size" min={300} max={1500} step={100} value={settings.chunkSize} onChange={(value) => updateSetting('chunkSize', value)} />
        <Slider label="Chunk overlap" min={0} max={300} step={20} value={settings.chunkOverlap} onChange={(value) => updateSetting('chunkOverlap', value)} />

        <Toggle label="Show source chunks" checked={showSources} onChange={setShowSources} />
        <Toggle
          label="Show debug workspace"
          checked={showDebug}
          onChange={(checked) => {
            setShowDebug(checked);
            if (checked) loadChunks();
          }}
        />

        <div className={`status ${health?.ok ? 'ready' : 'offline'}`}>
          <span>{health?.ok ? 'Ollama connected' : 'Ollama offline'}</span>
          <button type="button" onClick={refreshHealth} aria-label="Refresh Ollama status">
            <RefreshCw size={16} />
          </button>
        </div>

        <button className="apply-button" type="button" onClick={applySettings} disabled={busy || !state.hasDocument}>
          Apply settings
        </button>

        <button className="secondary" type="button" onClick={resetWorkspace} disabled={busy}>
          Reset workspace
        </button>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">PDF Copilot</p>
            <h2>Ask your document like it is sitting next to you.</h2>
          </div>
          {notice && <span className="notice">{notice}</span>}
        </header>

        <section className="stats" aria-label="Document stats">
          <Stat label="Document" value={state.docName || 'Waiting'} />
          <Stat label="Pages" value={state.pages} />
          <Stat label="Indexed Chunks" value={state.chunks} />
        </section>

        <section className="content-grid">
          <div className="panel">
            <div className="tabs">
              {['preview', 'prompts', 'debug'].map((tab) => (
                <button
                  className={activeTab === tab ? 'active' : ''}
                  key={tab}
                  type="button"
                  onClick={() => {
                    setActiveTab(tab);
                    if (tab === 'debug') loadChunks();
                  }}
                >
                  {tab}
                </button>
              ))}
            </div>

            {activeTab === 'preview' && (
              state.hasDocument ? (
                <iframe className="pdf-frame" src={pdfUrl} title="PDF preview" />
              ) : (
                <EmptyState text="Upload a PDF to unlock the preview pane." />
              )
            )}

            {activeTab === 'prompts' && (
              <div className="prompt-list">
                {prompts.map((prompt) => (
                  <button key={prompt} type="button" onClick={() => ask(prompt)} disabled={!state.hasDocument || busy}>
                    {prompt}
                  </button>
                ))}
              </div>
            )}

            {activeTab === 'debug' && (
              showDebug ? (
                <div className="chunk-list">
                  {chunks.length ? chunks.map((chunk) => (
                    <details key={chunk.index}>
                      <summary>Chunk {chunk.index} / Page {chunk.page}</summary>
                      <p>{chunk.content}</p>
                    </details>
                  )) : <EmptyState text="Debug chunks will show here after indexing." />}
                </div>
              ) : (
                <EmptyState text="Enable debug workspace to inspect chunks." />
              )
            )}
          </div>

          <div className="chat">
            <div className="chat-title">
              <Bot size={20} />
              <h3>Chat With Your PDF</h3>
            </div>

            <div className="messages">
              {messages.length === 0 && <EmptyState text="Upload a PDF, then ask anything about it." />}
              {messages.map((message, index) => (
                <Message key={`${message.role}-${index}`} message={message} showSources={showSources} />
              ))}
            </div>

            <form
              className="composer"
              onSubmit={(event) => {
                event.preventDefault();
                ask();
              }}
            >
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Ask something about the uploaded PDF..."
                disabled={!state.hasDocument || busy}
              />
              <button type="submit" disabled={!state.hasDocument || busy || !query.trim()} aria-label="Send question">
                {busy ? <Loader2 className="spin" size={18} /> : <ArrowUp size={18} />}
              </button>
            </form>
          </div>
        </section>
      </section>
    </main>
  );
}

function LandingPage({ onOpenBasic, onOpenSemrag, onOpenVectorlessRah }) {
  return (
    <main className="landing-page">
      <section className="landing-shell larger-landing-shell">
        <div className="landing-copy">
          <p className="eyebrow">Ledger</p>
          <SplitText
            text="Turn quiet PDFs into conversations."
            className="landing-title"
            delay={50}
            duration={1.25}
            ease="power3.out"
            splitType="chars"
            from={{ opacity: 0, y: 40 }}
            to={{ opacity: 1, y: 0 }}
            threshold={0.1}
            tag="h1"
          />
          <FadeContent blur={false} duration={800} ease="power2.out" initialOpacity={0}>
            <p>
              Ledger reads your document, breaks it into useful pieces, and lets you ask questions like the file finally learned how to talk back.
              Start with the simple RAG workspace today, then step into SemRAG when the smarter version is ready.
            </p>
          </FadeContent>
        </div>

        <div className="mode-grid">
          <FadeContent blur={false} duration={1000} delay={200} ease="power2.out" initialOpacity={0}>
            <button className="mode-card primary-mode floating-card" type="button" onClick={onOpenBasic}>
              <span className="mode-icon"><FileText size={24} /></span>
              <span>
                <strong>Basic RAG</strong>
                <small>PDF parsing, simple separator-based chunks, FAISS retrieval, and local chat.</small>
              </span>
            </button>
          </FadeContent>

          <FadeContent blur={false} duration={1000} delay={400} ease="power2.out" initialOpacity={0}>
            <button className="mode-card floating-card" type="button" onClick={onOpenSemrag}>
              <span className="mode-icon"><Sparkles size={24} /></span>
              <span>
                <strong>SemRAG</strong>
                <small>A semantic retrieval workspace is coming next.</small>
              </span>
            </button>
          </FadeContent>

          <FadeContent blur={false} duration={1000} delay={600} ease="power2.out" initialOpacity={0}>
            <button className="mode-card floating-card" type="button" onClick={onOpenVectorlessRah}>
              <span className="mode-icon"><Sparkles size={24} /></span>
              <span>
                <strong>Vectorless RAH</strong>
                <small>A vectorless retrieval workspace is coming next.</small>
              </span>
            </button>
          </FadeContent>
        </div>

        <div className="landing-strips" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
      </section>
    </main>
  );
}

function VectorlessRahPage({ onBack }) {
  return (
    <main className="landing-page">
      <section className="wip-shell">
        <button className="home-link" type="button" onClick={onBack}>
          <ArrowLeft size={16} />
          Back
        </button>
        <p className="eyebrow">Vectorless RAH</p>
        <h1>Work in progress.</h1>
        <p>
          This space is reserved for the vectorless retrieval version: alternative chunking, smarter context selection, and a more meaning-aware document brain.
        </p>
      </section>
    </main>
  );
}

function SemragPage({ onBack }) {
  return (
    <main className="landing-page">
      <section className="wip-shell">
        <button className="home-link" type="button" onClick={onBack}>
          <ArrowLeft size={16} />
          Back
        </button>
        <p className="eyebrow">SemRAG</p>
        <h1>Work in progress.</h1>
        <p>
          This space is reserved for the semantic retrieval version: richer chunking, smarter context selection, and a more meaning-aware document brain.
        </p>
      </section>
    </main>
  );
}

function Slider({ label, min, max, step = 1, value, onChange }) {
  return (
    <label className="field slider-field">
      <span className="slider-head">
        <span>{label}</span>
        <strong>{value}</strong>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
      />
      <span className="slider-scale">
        <small>{min}</small>
        <small>{max}</small>
      </span>
    </label>
  );
}

function Toggle({ label, checked, onChange }) {
  return (
    <label className="toggle">
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <span />
      {label}
    </label>
  );
}

function Stat({ label, value }) {
  return (
    <article className="stat">
      <p>{label}</p>
      <strong>{value}</strong>
    </article>
  );
}

function Message({ message, showSources }) {
  const Icon = message.role === 'user' ? User : Bot;
  return (
    <article className={`message ${message.role} ${message.error ? 'error' : ''}`}>
      <div className="avatar"><Icon size={16} /></div>
      <div>
        <p>{message.content}</p>
        {showSources && message.sources?.length > 0 && (
          <div className="sources">
            {message.sources.map((source, index) => (
              <details key={`${source.page}-${index}`}>
                <summary>Source {index + 1} / Page {source.page}</summary>
                <p>{source.content}</p>
              </details>
            ))}
          </div>
        )}
      </div>
    </article>
  );
}

function EmptyState({ text }) {
  return (
    <div className="empty">
      <FileText size={22} />
      <p>{text}</p>
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);
