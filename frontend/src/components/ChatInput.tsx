import { useEffect, useMemo, useState } from 'react';
import { Info, Loader2, SendHorizonal } from 'lucide-react';

type Props = {
  onSend: (options: {
    text: string;
    topK: number;
    debug: boolean;
    model: string;
    minScore: number;
  }) => Promise<void>;
  disabled?: boolean;
  models: string[];
  selectedModel: string;
  onModelChange: (model: string) => void;
  minScore: number;
  onMinScoreChange: (value: number) => void;
  prefillText?: string;
  onPrefillApplied?: () => void;
};

export function ChatInput({
  onSend,
  disabled,
  models,
  selectedModel,
  onModelChange,
  minScore,
  onMinScoreChange,
  prefillText,
  onPrefillApplied,
}: Props) {
  const [text, setText] = useState('');
  const [topK, setTopK] = useState(4);
  const [debug, setDebug] = useState(false);
  const [loading, setLoading] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);

  useEffect(() => {
    if (prefillText) {
      setText(prefillText);
      onPrefillApplied?.();
    }
  }, [prefillText, onPrefillApplied]);

  const InfoBadge = ({ text }: { text: string }) => (
    <span className="info-badge" role="tooltip" title={text} aria-label="More info">
      <Info size={14} />
    </span>
  );

  const topKHint = useMemo(() => {
    if (topK <= 3) return 'Snappy: fewer excerpts, faster answers.';
    if (topK >= 7) return 'Comprehensive: long answers with more citations.';
    return 'Balanced: equal mix of depth and focus.';
  }, [topK]);

  const minScorePercent = Math.round(minScore * 100);
  const scoreHint = useMemo(() => {
    if (minScorePercent <= 12) return 'Exploratory mode · cast a wider net.';
    if (minScorePercent >= 30) return 'Strict mode · only high-confidence chunks.';
    return 'Balanced mode · best of both worlds.';
  }, [minScorePercent]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!text.trim()) return;
    setLoading(true);
    try {
      await onSend({ text: text.trim(), topK, debug, model: selectedModel, minScore });
      setText('');
    } finally {
      setLoading(false);
    }
  }

  return (
    <form className="chat-input" onSubmit={handleSubmit}>
      <textarea
        placeholder="Ask anything you would ask a teammate..."
        value={text}
        onChange={(e) => setText(e.target.value)}
        disabled={disabled || loading}
        aria-label="Chat prompt"
      />
      <div className="input-hint">Press Shift + Enter for a newline. Answers cite sources automatically.</div>
      <div className="chat-input-toolbar">
        <button
          type="button"
          className="ghost-btn"
          onClick={() => setShowAdvanced((prev) => !prev)}
          style={{ marginRight: 'auto' }}
          aria-expanded={showAdvanced}
          aria-controls="advanced-panel"
        >
          {showAdvanced ? 'Hide guidance' : 'Guided options'}
        </button>
        <button className="primary" type="submit" disabled={loading || disabled} aria-label="Send message">
          {loading ? (
            <span className="inline-flex">
              <Loader2 size={16} className="spin" /> Thinking
            </span>
          ) : (
            <span className="inline-flex">
              Send <SendHorizonal size={16} />
            </span>
          )}
        </button>
      </div>
      {showAdvanced && (
        <div className="advanced-panel" id="advanced-panel">
          <RangeField
            label="Context window (Top K)"
            info="How many top-ranked chunks feed the prompt."
            min={1}
            max={10}
            step={1}
            value={topK}
            ariaLabel="Top K slider"
            onChange={setTopK}
            helper={topKHint}
            formatValue={(value) => `${value} chunks`}
          />
          <div className="field">
            <div className="field-header">
              <span>Model</span>
              <InfoBadge text="Choose among the allowed LLM runtimes exposed by the backend." />
            </div>
            <select value={selectedModel} onChange={(e) => onModelChange(e.target.value)} aria-label="Select model">
              {models.map((model) => (
                <option key={model} value={model}>
                  {model}
                </option>
              ))}
            </select>
            <p className="field-hint">Switch when you need a different context window or tone.</p>
          </div>
          <RangeField
            label="Min score threshold"
            info="Chunks must clear this hybrid score before hitting the LLM."
            min={0}
            max={100}
            step={1}
            value={minScorePercent}
            ariaLabel="Minimum score slider"
            onChange={(value) => onMinScoreChange(value / 100)}
            helper={scoreHint}
            formatValue={(value) => `${value}%`}
          />
          <label className="checkbox field full-span">
            <input
              type="checkbox"
              checked={debug}
              onChange={(e) => setDebug(e.target.checked)}
              aria-label="Toggle retrieval debug traces"
            />{' '}
            Debug traces
            <InfoBadge text="Adds retrieval diagnostics so you can inspect lexical/vector/graph contributions." />
          </label>
        </div>
      )}
    </form>
  );
}

type RangeFieldProps = {
  label: string;
  info: string;
  min: number;
  max: number;
  step: number;
  value: number;
  ariaLabel: string;
  onChange: (value: number) => void;
  helper: string;
  formatValue?: (value: number) => string;
};

function RangeField({
  label,
  info,
  min,
  max,
  step,
  value,
  ariaLabel,
  onChange,
  helper,
  formatValue,
}: RangeFieldProps) {
  const InfoBadge = ({ text }: { text: string }) => (
    <span className="info-badge" role="tooltip" title={text} aria-label="More info">
      <Info size={14} />
    </span>
  );
  return (
    <div className="field">
      <div className="field-header">
        <span>{label}</span>
        <span className="range-value">{formatValue ? formatValue(value) : value}</span>
      </div>
      <InfoBadge text={info} />
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        aria-label={ariaLabel}
      />
      <p className="field-hint">{helper}</p>
    </div>
  );
}
