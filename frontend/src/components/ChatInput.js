import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useMemo, useState } from 'react';
import { Info, Loader2, SendHorizonal } from 'lucide-react';
export function ChatInput({ onSend, disabled, models, selectedModel, onModelChange, minScore, onMinScoreChange, prefillText, onPrefillApplied, }) {
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
    const InfoBadge = ({ text }) => (_jsx("span", { className: "info-badge", role: "tooltip", title: text, "aria-label": "More info", children: _jsx(Info, { size: 14 }) }));
    const topKHint = useMemo(() => {
        if (topK <= 3)
            return 'Snappy: fewer excerpts, faster answers.';
        if (topK >= 7)
            return 'Comprehensive: long answers with more citations.';
        return 'Balanced: equal mix of depth and focus.';
    }, [topK]);
    const minScorePercent = Math.round(minScore * 100);
    const scoreHint = useMemo(() => {
        if (minScorePercent <= 12)
            return 'Exploratory mode · cast a wider net.';
        if (minScorePercent >= 30)
            return 'Strict mode · only high-confidence chunks.';
        return 'Balanced mode · best of both worlds.';
    }, [minScorePercent]);
    async function handleSubmit(event) {
        event.preventDefault();
        if (!text.trim())
            return;
        setLoading(true);
        try {
            await onSend({ text: text.trim(), topK, debug, model: selectedModel, minScore });
            setText('');
        }
        finally {
            setLoading(false);
        }
    }
    return (_jsxs("form", { className: "chat-input", onSubmit: handleSubmit, children: [_jsx("textarea", { placeholder: "Ask anything you would ask a teammate...", value: text, onChange: (e) => setText(e.target.value), disabled: disabled || loading, "aria-label": "Chat prompt" }), _jsx("div", { className: "input-hint", children: "Press Shift + Enter for a newline. Answers cite sources automatically." }), _jsxs("div", { className: "chat-input-toolbar", children: [_jsx("button", { type: "button", className: "ghost-btn", onClick: () => setShowAdvanced((prev) => !prev), style: { marginRight: 'auto' }, "aria-expanded": showAdvanced, "aria-controls": "advanced-panel", children: showAdvanced ? 'Hide guidance' : 'Guided options' }), _jsx("button", { className: "primary", type: "submit", disabled: loading || disabled, "aria-label": "Send message", children: loading ? (_jsxs("span", { className: "inline-flex", children: [_jsx(Loader2, { size: 16, className: "spin" }), " Thinking"] })) : (_jsxs("span", { className: "inline-flex", children: ["Send ", _jsx(SendHorizonal, { size: 16 })] })) })] }), showAdvanced && (_jsxs("div", { className: "advanced-panel", id: "advanced-panel", children: [_jsx(RangeField, { label: "Context window (Top K)", info: "How many top-ranked chunks feed the prompt.", min: 1, max: 10, step: 1, value: topK, ariaLabel: "Top K slider", onChange: setTopK, helper: topKHint, formatValue: (value) => `${value} chunks` }), _jsxs("div", { className: "field", children: [_jsxs("div", { className: "field-header", children: [_jsx("span", { children: "Model" }), _jsx(InfoBadge, { text: "Choose among the allowed LLM runtimes exposed by the backend." })] }), _jsx("select", { value: selectedModel, onChange: (e) => onModelChange(e.target.value), "aria-label": "Select model", children: models.map((model) => (_jsx("option", { value: model, children: model }, model))) }), _jsx("p", { className: "field-hint", children: "Switch when you need a different context window or tone." })] }), _jsx(RangeField, { label: "Min score threshold", info: "Chunks must clear this hybrid score before hitting the LLM.", min: 0, max: 100, step: 1, value: minScorePercent, ariaLabel: "Minimum score slider", onChange: (value) => onMinScoreChange(value / 100), helper: scoreHint, formatValue: (value) => `${value}%` }), _jsxs("label", { className: "checkbox field full-span", children: [_jsx("input", { type: "checkbox", checked: debug, onChange: (e) => setDebug(e.target.checked), "aria-label": "Toggle retrieval debug traces" }), ' ', "Debug traces", _jsx(InfoBadge, { text: "Adds retrieval diagnostics so you can inspect lexical/vector/graph contributions." })] })] }))] }));
}
function RangeField({ label, info, min, max, step, value, ariaLabel, onChange, helper, formatValue, }) {
    const InfoBadge = ({ text }) => (_jsx("span", { className: "info-badge", role: "tooltip", title: text, "aria-label": "More info", children: _jsx(Info, { size: 14 }) }));
    return (_jsxs("div", { className: "field", children: [_jsxs("div", { className: "field-header", children: [_jsx("span", { children: label }), _jsx("span", { className: "range-value", children: formatValue ? formatValue(value) : value })] }), _jsx(InfoBadge, { text: info }), _jsx("input", { type: "range", min: min, max: max, step: step, value: value, onChange: (e) => onChange(Number(e.target.value)), "aria-label": ariaLabel }), _jsx("p", { className: "field-hint", children: helper })] }));
}
