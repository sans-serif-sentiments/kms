import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { GitBranch, Database, Clock } from 'lucide-react';
export function StatusStrip({ health }) {
    return (_jsxs("div", { className: "card", style: { display: 'grid', gap: '1rem', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }, children: [_jsx(StatusTile, { icon: _jsx(GitBranch, { size: 18 }), label: "Repo", value: health?.repo || 'unknown' }), _jsx(StatusTile, { icon: _jsx(Database, { size: 18 }), label: "Units indexed", value: String(health?.units ?? 0) }), _jsx(StatusTile, { icon: _jsx(Clock, { size: 18 }), label: "Last indexed", value: health?.last_indexed_at || 'pending' })] }));
}
function StatusTile({ icon, label, value }) {
    return (_jsxs("div", { style: { display: 'flex', flexDirection: 'column', gap: '0.4rem' }, children: [_jsxs("span", { style: { display: 'flex', gap: '0.5rem', alignItems: 'center', color: '#475569' }, children: [icon, label] }), _jsx("strong", { style: { fontSize: '1.1rem' }, children: value })] }));
}
