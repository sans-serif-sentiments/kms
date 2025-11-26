import { useEffect, useState } from 'react';
import { Info } from 'lucide-react';
import { StatusStrip } from './components/StatusStrip';
import { ChatInput } from './components/ChatInput';
import { ChatTranscript, ConversationMessage } from './components/ChatTranscript';
import { UploadPanel } from './components/UploadPanel';
import type { HealthInfo, SourceInfo } from './lib/api';
import { createSession, fetchHealth, fetchModels, loadSession, runQuery } from './lib/api';

const NAME_KEY = 'ai-kms-name';
const SESSION_KEY = 'ai-kms-session';

const QUICK_PROMPTS = [
  {
    label: 'Policy',
    prompt: 'Who approves PTO longer than 10 days?',
    description: 'Great for HR/policy flows—prompts the assistant to cite HR units.',
  },
  {
    label: 'Sales',
    prompt: 'Sales AI assistant isn’t logging notes. How do I escalate?',
    description: 'Use when GTM teams need escalation or trust briefs.',
  },
  {
    label: 'Wellness',
    prompt: 'I feel burnt out—what support do we offer?',
    description: 'Triggers wellbeing context and HR contacts.',
  },
  {
    label: 'LangGraph',
    prompt: 'Give me a quick overview of LangGraph ownership.',
    description: 'Route orchestration/agent questions to the LangGraph docs.',
  },
  {
    label: 'World / General',
    prompt: 'Explain the latest world economy update',
    description: 'Use with the general-knowledge toggle for external summaries.',
    variant: 'outline',
  },
];

export default function App() {
  const [health, setHealth] = useState<HealthInfo>();
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<'chat' | 'upload'>('chat');
  const [models, setModels] = useState<string[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>('llama3.2:3b');
  const [sessionId, setSessionId] = useState<string>();
  const [displayName, setDisplayName] = useState<string>('');
  const [sessionLoading, setSessionLoading] = useState<boolean>(true);
  const [minScore, setMinScore] = useState<number>(0.15);
  const [prefillText, setPrefillText] = useState<string>();
  const [allowExternal, setAllowExternal] = useState<boolean>(false);
  const [activePrompt, setActivePrompt] = useState<string | null>(null);

  useEffect(() => {
    fetchHealth().then(setHealth).catch(() => setHealth(undefined));
    if (typeof window !== 'undefined') {
      const storedName = localStorage.getItem(NAME_KEY);
      if (storedName) {
        setDisplayName(storedName);
      }
      const storedSession = localStorage.getItem(SESSION_KEY);
      if (storedSession) {
        resumeSession(storedSession, storedName || undefined);
        return;
      }
      startSession(storedName || undefined);
    } else {
      startSession();
    }
  }, []);

  useEffect(() => {
    fetchModels()
      .then((list) => {
        setModels(list.allowed);
        setSelectedModel(list.default);
      })
      .catch(() => setModels([]));
  }, []);

  async function startSession(name?: string): Promise<string | undefined> {
    setSessionLoading(true);
    try {
      const session = await createSession(name);
      setSessionId(session.session_id);
      if (session.name) {
        setDisplayName(session.name);
        if (typeof window !== 'undefined') {
          localStorage.setItem(NAME_KEY, session.name);
        }
      }
      if (typeof window !== 'undefined') {
        localStorage.setItem(SESSION_KEY, session.session_id);
      }
      setMessages([{ role: 'assistant', content: session.greeting }]);
      return session.session_id;
    } catch (err) {
      setMessages([
        {
          role: 'assistant',
          content: "Hi! I'm your AI-KMS teammate. Ask about policies, processes, or enablement docs and I'll cite my sources.",
        },
      ]);
      return undefined;
    } finally {
      setSessionLoading(false);
    }
  }

  async function resumeSession(sessionId: string, name?: string): Promise<string | undefined> {
    setSessionLoading(true);
    try {
      const session = await loadSession(sessionId);
      setSessionId(session.session_id);
      if (session.name) {
        setDisplayName(session.name);
        if (typeof window !== 'undefined') {
          localStorage.setItem(NAME_KEY, session.name);
        }
      } else if (name) {
        setDisplayName(name);
      }
      const restored = session.messages.map((message) => ({
        role: message.role,
        content: message.content,
        sources: Array.isArray(message.metadata?.sources) ? (message.metadata?.sources as SourceInfo[]) : undefined,
        confidence:
          typeof message.metadata?.confidence === 'string'
            ? (message.metadata?.confidence as string)
            : undefined,
        sourceType:
          typeof message.metadata?.source_type === 'string'
            ? (message.metadata?.source_type as string)
            : undefined,
      }));
      setMessages(restored);
      if (typeof window !== 'undefined') {
        localStorage.setItem(SESSION_KEY, session.session_id);
      }
      return session.session_id;
    } catch (err) {
      console.warn('Failed to resume session, creating new one', err);
      return await startSession(name);
    } finally {
      setSessionLoading(false);
    }
  }

  async function handleSend(args: { text: string; topK: number; debug: boolean; minScore: number }) {
    await sendMessage({ ...args, allowExternal });
  }

  async function sendMessage(
    {
      text,
      topK,
      debug,
      minScore: localMinScore,
      allowExternal: externalAllowed,
    }: { text: string; topK: number; debug: boolean; minScore: number; allowExternal: boolean },
    isRetry = false
  ): Promise<void> {
    setLoading(true);
    let activeSession = sessionId;
    if (!activeSession) {
      activeSession = await startSession(displayName || undefined);
    }
    if (!activeSession) {
      setLoading(false);
      return;
    }
    setSessionId(activeSession);
    if (typeof window !== 'undefined') {
      localStorage.setItem(SESSION_KEY, activeSession);
    }
    setMessages((prev) => [...prev, { role: 'user', content: text }]);
    try {
      const response = await runQuery({
        question: text,
        top_k: topK,
        debug,
        history: [],
        model: selectedModel,
        session_id: activeSession,
        min_score_threshold: localMinScore,
        allow_external: externalAllowed,
      });
      if (response.session_id && response.session_id !== activeSession) {
        setSessionId(response.session_id);
        if (typeof window !== 'undefined') {
          localStorage.setItem(SESSION_KEY, response.session_id);
        }
      }
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: response.answer,
          sources: response.sources,
          confidence: response.confidence,
          sourceType: response.source_type,
        },
      ]);
      setActivePrompt(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch backend response';
      if (!isRetry && message.includes('session_not_found')) {
        await startSession(displayName || undefined);
        setMessages((prev) => [
          ...prev,
          { role: 'assistant', content: 'Previous session expired. Starting a new chat...' },
        ]);
        setLoading(false);
        return sendMessage({ text, topK, debug, minScore: localMinScore, allowExternal: externalAllowed }, true);
      }
      setMessages((prev) => [...prev, { role: 'assistant', content: `Error: ${message}` }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app-shell">
      <header style={{ marginBottom: '1rem' }}>
        <p className="badge" style={{ background: '#dbeafe', color: '#1d4ed8' }}>Local-first</p>
        <h1 style={{ marginBottom: '0.3rem' }}>AI-KMS Knowledge Console</h1>
        <p style={{ color: '#475569' }}>
          Chat with the GitHub-sourced knowledge base as if you were messaging a teammate. Answers always cite their sources and
          can explain when information is missing. If you ask about public or world topics, I’ll note when the response comes
          from outside the internal KB.
        </p>
      </header>
      <StatusStrip health={health} />
      <div className="tab-bar">
        <button
          className={`tab-btn ${activeTab === 'chat' ? 'active' : ''}`}
          onClick={() => setActiveTab('chat')}
          aria-label="Chat with KB"
        >
          Chat
        </button>
        <button
          className={`tab-btn ${activeTab === 'upload' ? 'active' : ''}`}
          onClick={() => setActiveTab('upload')}
          aria-label="Upload KB doc"
        >
          Upload KB
        </button>
      </div>
      {activeTab === 'upload' && <UploadPanel />}
      {activeTab === 'chat' && (
      <div className="chat-layout">
        <div className="card session-panel">
          <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
            <label style={{ flexGrow: 1 }}>
              Display name
              <input
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="Your name"
              />
              <small className="input-hint">Used in transcripts and greetings—leave blank for anonymous sessions.</small>
            </label>
            <button className="primary" type="button" onClick={() => startSession(displayName || undefined)}>
              Start new session
            </button>
            {(() => {
              const pending = sessionLoading || !sessionId;
              return (
                <span className={`status-pill ${pending ? 'pending' : 'ready'}`} role="status">
                  <span className="status-dot" />
                  <span className="status-text">
                    {pending ? 'Initializing session' : `Session ${sessionId?.slice(0, 6)}`}
                  </span>
                </span>
              );
            })()}
            <button
              type="button"
              className="ghost-btn"
              onClick={() => {
                const transcript = messages
                  .map((m) => `${m.role.toUpperCase()}:\n${m.content}\n`)
                  .join('\\n-----------------------\\n');
                const blob = new Blob([transcript], { type: 'text/plain' });
                const url = URL.createObjectURL(blob);
                const link = document.createElement('a');
                link.href = url;
                link.download = `ai-kms-session-${Date.now()}.txt`;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                URL.revokeObjectURL(url);
              }}
              disabled={!messages.length}
            >
              Export transcript
            </button>
          </div>
        </div>
        <ChatTranscript messages={messages} />
        <div className="quick-intent-grid" role="list" aria-label="Quick prompts">
          <span>Quick prompts:</span>
          {QUICK_PROMPTS.map((item) => (
            <button
              key={item.label}
              className={`intent-pill ${item.variant ?? ''} ${activePrompt === item.label ? 'active' : ''}`}
              type="button"
              role="listitem"
              aria-label={`Prefill question about ${item.label}`}
              onClick={() => {
                setPrefillText(item.prompt);
                setActivePrompt(item.label);
              }}
            >
              {item.label}
            </button>
          ))}
          <div className="prompt-hint">
            <Info size={14} />
            <p>
              {activePrompt
                ? QUICK_PROMPTS.find((p) => p.label === activePrompt)?.description
                : 'Pick a quick prompt to see suggested questions and learn which intents they target.'}
            </p>
          </div>
          <small className="input-hint">When you ask world questions, replies are labeled “External context”.</small>
        </div>
        <div className="external-toggle" aria-live="polite">
          <div className="external-copy">
            <span>General knowledge answers</span>
            <InfoBadge text="Let the assistant answer world/general questions using the external model. Replies are labeled “External context”." />
            <p>Turn this on when your question falls outside the KB.</p>
          </div>
          <label className="toggle-switch">
            <input
              type="checkbox"
              checked={allowExternal}
              onChange={(e) => setAllowExternal(e.target.checked)}
              aria-label="Allow general knowledge answers"
            />
            <span className="slider" />
          </label>
        </div>
        {loading && (
          <div className="typing-card" role="status" aria-live="polite">
            <div className="typing-dots">
              <span className="typing-bubble" />
              <span className="typing-bubble" />
              <span className="typing-bubble" />
            </div>
            <span>Assistant is preparing a response...</span>
          </div>
        )}
        <ChatInput
          onSend={handleSend}
          disabled={loading || sessionLoading || !sessionId}
          models={models.length ? models : [selectedModel]}
          selectedModel={selectedModel}
          onModelChange={setSelectedModel}
          minScore={minScore}
          onMinScoreChange={setMinScore}
          prefillText={prefillText}
          onPrefillApplied={() => {
            setPrefillText(undefined);
            setActivePrompt(null);
          }}
        />
      </div>
      )}
    </div>
  );
}

function InfoBadge({ text }: { text: string }) {
  return (
    <span className="info-badge" role="tooltip" title={text} aria-label="More info">
      <Info size={14} />
    </span>
  );
}
