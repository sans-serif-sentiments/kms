import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { Files, Copy, Mail, Download, Shield } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
const CONFIDENCE_COPY = {
    high: { label: 'High confidence', description: 'Multiple corroborating chunks. Safe to rely on.' },
    medium: { label: 'Medium confidence', description: 'Some coverage, but double-check edge cases.' },
    low: { label: 'Low confidence', description: 'Please review citations or contact an owner.' },
};
function deriveConfidence(explicitLevel, sourcesCount) {
    const normalized = explicitLevel?.toLowerCase();
    if (normalized === 'high' || normalized === 'medium' || normalized === 'low') {
        const copy = CONFIDENCE_COPY[normalized];
        return { level: normalized, ...copy };
    }
    if (sourcesCount >= 3)
        return { level: 'high', ...CONFIDENCE_COPY.high };
    if (sourcesCount >= 1)
        return { level: 'medium', ...CONFIDENCE_COPY.medium };
    return { level: 'low', ...CONFIDENCE_COPY.low };
}
const SectionHeading = (props) => (_jsx("div", { className: "section-heading", ...props }));
export function ChatTranscript({ messages }) {
    const downloadText = (content) => {
        const blob = new Blob([content], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `ai-kms-response-${Date.now()}.txt`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    };
    if (!messages.length) {
        return (_jsx("div", { className: "chat-transcript", children: _jsx("p", { style: { color: '#475569' }, children: "Conversations appear here. Ask the assistant anything from user data definitions to enablement policies." }) }));
    }
    return (_jsx("div", { className: "chat-transcript", children: messages.map((message, index) => {
            const confidence = message.role === 'assistant'
                ? deriveConfidence(message.confidence, message.sources?.length ?? 0)
                : null;
            return (_jsx("div", { className: `chat-message ${message.role}`, children: _jsxs("div", { className: "bubble", children: [_jsx("strong", { style: { display: 'block', marginBottom: '0.35rem' }, children: message.role === 'user' ? 'You' : 'Assistant' }), _jsx(ReactMarkdown, { className: "assistant-markdown", components: {
                                h1: (props) => _jsx(SectionHeading, { ...props }),
                                h2: (props) => _jsx(SectionHeading, { ...props }),
                                h3: (props) => _jsx(SectionHeading, { ...props }),
                                ul: (props) => _jsx("ul", { className: "markdown-list", ...props }),
                            }, children: message.content }), message.role === 'assistant' && (_jsxs(_Fragment, { children: [_jsxs("div", { style: { marginTop: '0.5rem', display: 'flex', gap: '0.6rem', flexWrap: 'wrap' }, children: [_jsxs("button", { className: "ghost-btn", onClick: () => navigator.clipboard.writeText(message.content), "aria-label": "Copy answer", children: [_jsx(Copy, { size: 14 }), " Copy"] }), _jsxs("a", { className: "ghost-btn", href: `mailto:?subject=Follow-up from AI-KMS Assistant&body=${encodeURIComponent(message.content)}`, "aria-label": "Draft email with response", children: [_jsx(Mail, { size: 14 }), " Draft email"] }), _jsxs("button", { className: "ghost-btn", onClick: () => downloadText(message.content), "aria-label": "Download answer", children: [_jsx(Download, { size: 14 }), " Download"] })] }), confidence && (_jsxs("div", { className: `confidence-meter ${confidence.level}`, "aria-live": "polite", children: [_jsxs("div", { className: "confidence-header", children: [_jsx(Shield, { size: 14 }), _jsx("span", { children: confidence.label })] }), _jsx("p", { className: "confidence-desc", children: confidence.description })] })), message.sourceType && (_jsx("div", { className: `source-chip ${message.sourceType}`, children: message.sourceType === 'external'
                                        ? 'External context (not from KB)'
                                        : message.sourceType === 'conversation'
                                            ? 'Conversational guidance'
                                            : 'Internal KB context' }))] })), message.sources && (_jsxs("div", { style: { marginTop: '0.6rem', fontSize: '0.85rem', color: '#475569' }, children: [_jsx(Files, { size: 14, style: { marginRight: '0.3rem' } }), " Sources (", message.sources.length, "):", message.sources.length > 0 ? (_jsx("ul", { className: "sources-list", children: message.sources.map((src) => {
                                        const label = src.title || src.source_path;
                                        return (_jsxs("li", { children: [_jsx("span", { className: "badge", children: src.knowledge_unit_id }), ' ', src.web_url ? (_jsx("a", { href: src.web_url, target: "_blank", rel: "noreferrer", children: label })) : (label)] }, `${src.knowledge_unit_id}-${src.section}`));
                                    }) })) : (_jsx("div", { style: { fontStyle: 'italic' }, children: "No citations for this reply." }))] }))] }) }, index));
        }) }));
}
