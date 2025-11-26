import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from 'react';
import { Info } from 'lucide-react';
import { StatusStrip } from './components/StatusStrip';
import { ChatInput } from './components/ChatInput';
import { ChatTranscript } from './components/ChatTranscript';
import { UploadPanel } from './components/UploadPanel';
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
    const [health, setHealth] = useState();
    const [messages, setMessages] = useState([]);
    const [loading, setLoading] = useState(false);
    const [activeTab, setActiveTab] = useState('chat');
    const [models, setModels] = useState([]);
    const [selectedModel, setSelectedModel] = useState('llama3.2:3b');
    const [sessionId, setSessionId] = useState();
    const [displayName, setDisplayName] = useState('');
    const [sessionLoading, setSessionLoading] = useState(true);
    const [minScore, setMinScore] = useState(0.15);
    const [prefillText, setPrefillText] = useState();
    const [allowExternal, setAllowExternal] = useState(false);
    const [activePrompt, setActivePrompt] = useState(null);
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
        }
        else {
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
    async function startSession(name) {
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
        }
        catch (err) {
            setMessages([
                {
                    role: 'assistant',
                    content: "Hi! I'm your AI-KMS teammate. Ask about policies, processes, or enablement docs and I'll cite my sources.",
                },
            ]);
            return undefined;
        }
        finally {
            setSessionLoading(false);
        }
    }
    async function resumeSession(sessionId, name) {
        setSessionLoading(true);
        try {
            const session = await loadSession(sessionId);
            setSessionId(session.session_id);
            if (session.name) {
                setDisplayName(session.name);
                if (typeof window !== 'undefined') {
                    localStorage.setItem(NAME_KEY, session.name);
                }
            }
            else if (name) {
                setDisplayName(name);
            }
            const restored = session.messages.map((message) => ({
                role: message.role,
                content: message.content,
                sources: Array.isArray(message.metadata?.sources) ? message.metadata?.sources : undefined,
                confidence: typeof message.metadata?.confidence === 'string'
                    ? message.metadata?.confidence
                    : undefined,
                sourceType: typeof message.metadata?.source_type === 'string'
                    ? message.metadata?.source_type
                    : undefined,
            }));
            setMessages(restored);
            if (typeof window !== 'undefined') {
                localStorage.setItem(SESSION_KEY, session.session_id);
            }
            return session.session_id;
        }
        catch (err) {
            console.warn('Failed to resume session, creating new one', err);
            return await startSession(name);
        }
        finally {
            setSessionLoading(false);
        }
    }
    async function handleSend(args) {
        await sendMessage({ ...args, allowExternal });
    }
    async function sendMessage({ text, topK, debug, minScore: localMinScore, allowExternal: externalAllowed, }, isRetry = false) {
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
        }
        catch (err) {
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
        }
        finally {
            setLoading(false);
        }
    }
    return (_jsxs("div", { className: "app-shell", children: [_jsxs("header", { style: { marginBottom: '1rem' }, children: [_jsx("p", { className: "badge", style: { background: '#dbeafe', color: '#1d4ed8' }, children: "Local-first" }), _jsx("h1", { style: { marginBottom: '0.3rem' }, children: "AI-KMS Knowledge Console" }), _jsx("p", { style: { color: '#475569' }, children: "Chat with the GitHub-sourced knowledge base as if you were messaging a teammate. Answers always cite their sources and can explain when information is missing. If you ask about public or world topics, I\u2019ll note when the response comes from outside the internal KB." })] }), _jsx(StatusStrip, { health: health }), _jsxs("div", { className: "tab-bar", children: [_jsx("button", { className: `tab-btn ${activeTab === 'chat' ? 'active' : ''}`, onClick: () => setActiveTab('chat'), "aria-label": "Chat with KB", children: "Chat" }), _jsx("button", { className: `tab-btn ${activeTab === 'upload' ? 'active' : ''}`, onClick: () => setActiveTab('upload'), "aria-label": "Upload KB doc", children: "Upload KB" })] }), activeTab === 'upload' && _jsx(UploadPanel, {}), activeTab === 'chat' && (_jsxs("div", { className: "chat-layout", children: [_jsx("div", { className: "card session-panel", children: _jsxs("div", { style: { display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap' }, children: [_jsxs("label", { style: { flexGrow: 1 }, children: ["Display name", _jsx("input", { type: "text", value: displayName, onChange: (e) => setDisplayName(e.target.value), placeholder: "Your name" }), _jsx("small", { className: "input-hint", children: "Used in transcripts and greetings\u2014leave blank for anonymous sessions." })] }), _jsx("button", { className: "primary", type: "button", onClick: () => startSession(displayName || undefined), children: "Start new session" }), (() => {
                                    const pending = sessionLoading || !sessionId;
                                    return (_jsxs("span", { className: `status-pill ${pending ? 'pending' : 'ready'}`, role: "status", children: [_jsx("span", { className: "status-dot" }), _jsx("span", { className: "status-text", children: pending ? 'Initializing session' : `Session ${sessionId?.slice(0, 6)}` })] }));
                                })(), _jsx("button", { type: "button", className: "ghost-btn", onClick: () => {
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
                                    }, disabled: !messages.length, children: "Export transcript" })] }) }), _jsx(ChatTranscript, { messages: messages }), _jsxs("div", { className: "quick-intent-grid", role: "list", "aria-label": "Quick prompts", children: [_jsx("span", { children: "Quick prompts:" }), QUICK_PROMPTS.map((item) => (_jsx("button", { className: `intent-pill ${item.variant ?? ''} ${activePrompt === item.label ? 'active' : ''}`, type: "button", role: "listitem", "aria-label": `Prefill question about ${item.label}`, onClick: () => {
                                    setPrefillText(item.prompt);
                                    setActivePrompt(item.label);
                                }, children: item.label }, item.label))), _jsxs("div", { className: "prompt-hint", children: [_jsx(Info, { size: 14 }), _jsx("p", { children: activePrompt
                                            ? QUICK_PROMPTS.find((p) => p.label === activePrompt)?.description
                                            : 'Pick a quick prompt to see suggested questions and learn which intents they target.' })] }), _jsx("small", { className: "input-hint", children: "When you ask world questions, replies are labeled \u201CExternal context\u201D." })] }), _jsxs("div", { className: "external-toggle", "aria-live": "polite", children: [_jsxs("div", { className: "external-copy", children: [_jsx("span", { children: "General knowledge answers" }), _jsx(InfoBadge, { text: "Let the assistant answer world/general questions using the external model. Replies are labeled \u201CExternal context\u201D." }), _jsx("p", { children: "Turn this on when your question falls outside the KB." })] }), _jsxs("label", { className: "toggle-switch", children: [_jsx("input", { type: "checkbox", checked: allowExternal, onChange: (e) => setAllowExternal(e.target.checked), "aria-label": "Allow general knowledge answers" }), _jsx("span", { className: "slider" })] })] }), loading && (_jsxs("div", { className: "typing-card", role: "status", "aria-live": "polite", children: [_jsxs("div", { className: "typing-dots", children: [_jsx("span", { className: "typing-bubble" }), _jsx("span", { className: "typing-bubble" }), _jsx("span", { className: "typing-bubble" })] }), _jsx("span", { children: "Assistant is preparing a response..." })] })), _jsx(ChatInput, { onSend: handleSend, disabled: loading || sessionLoading || !sessionId, models: models.length ? models : [selectedModel], selectedModel: selectedModel, onModelChange: setSelectedModel, minScore: minScore, onMinScoreChange: setMinScore, prefillText: prefillText, onPrefillApplied: () => {
                            setPrefillText(undefined);
                            setActivePrompt(null);
                        } })] }))] }));
}
function InfoBadge({ text }) {
    return (_jsx("span", { className: "info-badge", role: "tooltip", title: text, "aria-label": "More info", children: _jsx(Info, { size: 14 }) }));
}
