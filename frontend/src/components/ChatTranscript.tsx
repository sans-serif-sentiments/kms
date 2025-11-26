import type { HTMLAttributes } from 'react';
import type { ChatRole, SourceInfo } from '../lib/api';
import { Files, Copy, Mail, Download, Shield } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

export interface ConversationMessage {
  role: ChatRole;
  content: string;
  sources?: SourceInfo[];
  confidence?: string;
  sourceType?: string;
}

type Props = {
  messages: ConversationMessage[];
};

type ConfidenceLevel = 'low' | 'medium' | 'high';

const CONFIDENCE_COPY: Record<ConfidenceLevel, { label: string; description: string }> = {
  high: { label: 'High confidence', description: 'Multiple corroborating chunks. Safe to rely on.' },
  medium: { label: 'Medium confidence', description: 'Some coverage, but double-check edge cases.' },
  low: { label: 'Low confidence', description: 'Please review citations or contact an owner.' },
};

function deriveConfidence(explicitLevel: string | undefined, sourcesCount: number): {
  level: ConfidenceLevel;
  label: string;
  description: string;
} {
  const normalized = explicitLevel?.toLowerCase();
  if (normalized === 'high' || normalized === 'medium' || normalized === 'low') {
    const copy = CONFIDENCE_COPY[normalized];
    return { level: normalized, ...copy };
  }
  if (sourcesCount >= 3) return { level: 'high', ...CONFIDENCE_COPY.high };
  if (sourcesCount >= 1) return { level: 'medium', ...CONFIDENCE_COPY.medium };
  return { level: 'low', ...CONFIDENCE_COPY.low };
}

const SectionHeading = (props: HTMLAttributes<HTMLDivElement>) => (
  <div className="section-heading" {...props} />
);

export function ChatTranscript({ messages }: Props) {
  const downloadText = (content: string) => {
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
    return (
      <div className="chat-transcript">
        <p style={{ color: '#475569' }}>
          Conversations appear here. Ask the assistant anything from user data definitions to enablement policies.
        </p>
      </div>
    );
  }
  return (
    <div className="chat-transcript">
      {messages.map((message, index) => {
        const confidence =
          message.role === 'assistant'
            ? deriveConfidence(message.confidence, message.sources?.length ?? 0)
            : null;
        return (
          <div key={index} className={`chat-message ${message.role}`}>
            <div className="bubble">
              <strong style={{ display: 'block', marginBottom: '0.35rem' }}>{message.role === 'user' ? 'You' : 'Assistant'}</strong>
              <ReactMarkdown
                className="assistant-markdown"
                components={{
                  h1: (props) => <SectionHeading {...props} />,
                  h2: (props) => <SectionHeading {...props} />,
                  h3: (props) => <SectionHeading {...props} />,
                  ul: (props) => <ul className="markdown-list" {...props} />,
                }}
              >
                {message.content}
              </ReactMarkdown>
              {message.role === 'assistant' && (
                <>
                  <div style={{ marginTop: '0.5rem', display: 'flex', gap: '0.6rem', flexWrap: 'wrap' }}>
                    <button className="ghost-btn" onClick={() => navigator.clipboard.writeText(message.content)} aria-label="Copy answer">
                      <Copy size={14} /> Copy
                    </button>
                    <a
                      className="ghost-btn"
                      href={`mailto:?subject=Follow-up from AI-KMS Assistant&body=${encodeURIComponent(message.content)}`}
                      aria-label="Draft email with response"
                    >
                      <Mail size={14} /> Draft email
                    </a>
                    <button className="ghost-btn" onClick={() => downloadText(message.content)} aria-label="Download answer">
                      <Download size={14} /> Download
                    </button>
                  </div>
                  {confidence && (
                    <div className={`confidence-meter ${confidence.level}`} aria-live="polite">
                      <div className="confidence-header">
                        <Shield size={14} />
                        <span>{confidence.label}</span>
                      </div>
                      <p className="confidence-desc">{confidence.description}</p>
                    </div>
                  )}
                  {message.sourceType && (
                    <div className={`source-chip ${message.sourceType}`}>
                      {message.sourceType === 'external'
                        ? 'External context (not from KB)'
                        : message.sourceType === 'conversation'
                        ? 'Conversational guidance'
                        : 'Internal KB context'}
                    </div>
                  )}
                </>
              )}
              {message.sources && (
                <div style={{ marginTop: '0.6rem', fontSize: '0.85rem', color: '#475569' }}>
                  <Files size={14} style={{ marginRight: '0.3rem' }} /> Sources ({message.sources.length}):
                  {message.sources.length > 0 ? (
                    <ul className="sources-list">
                      {message.sources.map((src) => {
                        const label = src.title || src.source_path;
                        return (
                          <li key={`${src.knowledge_unit_id}-${src.section}`}>
                            <span className="badge">{src.knowledge_unit_id}</span>{' '}
                            {src.web_url ? (
                              <a href={src.web_url} target="_blank" rel="noreferrer">
                                {label}
                              </a>
                            ) : (
                              label
                            )}
                          </li>
                        );
                      })}
                    </ul>
                  ) : (
                    <div style={{ fontStyle: 'italic' }}>No citations for this reply.</div>
                  )}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
