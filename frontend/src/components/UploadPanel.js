import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import { Info, UploadCloud } from 'lucide-react';
import { uploadDoc, uploadFile } from '../lib/api';
export function UploadPanel({ onSuccess }) {
    const [id, setId] = useState('');
    const [title, setTitle] = useState('');
    const [category, setCategory] = useState('faq');
    const [body, setBody] = useState('');
    const [contacts, setContacts] = useState('');
    const [tags, setTags] = useState('');
    const [status, setStatus] = useState(null);
    const [preview, setPreview] = useState(null);
    const [loading, setLoading] = useState(false);
    const [file, setFile] = useState(null);
    const contactTemplates = [
        { label: 'LangGraph Docs Steward', line: 'LangGraph Docs Steward | langgraph-docs@company.com' },
        { label: 'Knowledge Steward', line: 'Knowledge Steward | knowledge@company.com' },
        { label: 'Compliance', line: 'Compliance Program Manager | compliance@company.com' },
    ];
    const handleSubmit = async (e, dryRun = false) => {
        e.preventDefault();
        setLoading(true);
        setStatus(null);
        setPreview(null);
        try {
            let res;
            if (file) {
                const form = new FormData();
                form.append('file', file);
                form.append('id', id);
                form.append('title', title);
                form.append('category', category);
                form.append('tags', tags);
                form.append('version', '0.1.0');
                form.append('contacts', contacts);
                form.append('dry_run', String(dryRun));
                res = await uploadFile(form);
            }
            else {
                const payload = {
                    id,
                    title,
                    category,
                    body,
                    tags: tags ? tags.split(',').map((t) => t.trim()).filter(Boolean) : [],
                    contacts: contacts
                        ? contacts.split('\n').map((line) => {
                            const [name, email] = line.split('|').map((p) => p.trim());
                            return { name, email };
                        })
                        : [],
                    version: '0.1.0',
                    dry_run: dryRun,
                };
                res = await uploadDoc(payload);
            }
            const pathDisplay = res.path ? res.path : res.paths ? res.paths.join(', ') : 'n/a';
            if (dryRun) {
                setStatus(`Validated. Target: ${pathDisplay}`);
                setPreview(res.preview_text || 'No preview available.');
            }
            else {
                setStatus(`Uploaded to ${pathDisplay} (indexed ${res.indexed}, chunks ${res.chunks})`);
                if (onSuccess)
                    onSuccess(res.path || pathDisplay);
                setId('');
                setTitle('');
                setBody('');
                setContacts('');
                setTags('');
                setFile(null);
            }
        }
        catch (err) {
            setStatus(err instanceof Error ? err.message : 'Upload failed');
        }
        finally {
            setLoading(false);
        }
    };
    return (_jsxs("div", { className: "card upload-panel", children: [_jsx("div", { className: "upload-header", children: _jsxs("div", { children: [_jsx("p", { className: "badge", children: "Beta" }), _jsx("h2", { children: "Quick KB Upload" }), _jsx("p", { className: "upload-hint", children: "Add docs with required metadata. Use Preview to normalize PDFs/Excel before ingest." })] }) }), _jsxs("div", { className: "upload-sections", children: [_jsxs("div", { className: "upload-card", children: [_jsxs("div", { className: "upload-card-head", children: [_jsx("span", { children: "Metadata" }), _jsx(HoverInfo, { text: "ID must follow KB naming (e.g., LG-XXX). Title and category are required." })] }), _jsxs("div", { className: "upload-form", onSubmit: (e) => handleSubmit(e, false), children: [_jsxs("div", { className: "field", children: [_jsxs("label", { children: ["KB ID ", _jsx(HoverInfo, { text: "Use prefixes like LG-, HR-, FIN-. Avoid spaces." })] }), _jsx("input", { value: id, onChange: (e) => setId(e.target.value), placeholder: "LG-NEW-DOC", required: true })] }), _jsxs("div", { className: "field", children: [_jsxs("label", { children: ["Title ", _jsx(HoverInfo, { text: "Human-readable doc title." })] }), _jsx("input", { value: title, onChange: (e) => setTitle(e.target.value), placeholder: "Doc title", required: true })] }), _jsxs("div", { className: "field", children: [_jsxs("label", { children: ["Category ", _jsx(HoverInfo, { text: "Must match allowed categories (faq, process, policy, concept, langraph, pattern)." })] }), _jsxs("select", { value: category, onChange: (e) => setCategory(e.target.value), children: [_jsx("option", { value: "faq", children: "faq" }), _jsx("option", { value: "process", children: "process" }), _jsx("option", { value: "policy", children: "policy" }), _jsx("option", { value: "concept", children: "concept" }), _jsx("option", { value: "langraph", children: "langraph" }), _jsx("option", { value: "pattern", children: "pattern" })] })] }), _jsxs("div", { className: "field", children: [_jsxs("label", { children: ["Tags ", _jsx(HoverInfo, { text: "Comma-separated tags to improve retrieval." })] }), _jsx("input", { value: tags, onChange: (e) => setTags(e.target.value), placeholder: "langgraph, ingestion" })] })] })] }), _jsxs("div", { className: "upload-card", children: [_jsxs("div", { className: "upload-card-head", children: [_jsx("span", { children: "Ownership" }), _jsx(HoverInfo, { text: "Contacts are required. Pick a template or add one per line: name | email." })] }), _jsxs("div", { className: "upload-form", children: [_jsxs("div", { className: "field", children: [_jsx("label", { children: "Contact templates" }), _jsxs("select", { onChange: (e) => {
                                                    if (!e.target.value)
                                                        return;
                                                    setContacts((prev) => (prev ? `${prev}\n${e.target.value}` : e.target.value));
                                                    e.target.selectedIndex = 0;
                                                }, children: [_jsx("option", { value: "", children: "Select a template" }), contactTemplates.map((tpl) => (_jsx("option", { value: tpl.line, children: tpl.label }, tpl.label)))] })] }), _jsxs("div", { className: "field full-span", children: [_jsxs("label", { children: ["Contacts ", _jsx(HoverInfo, { text: "One per line: name | email. Required for ingestion." })] }), _jsx("textarea", { rows: 3, value: contacts, onChange: (e) => setContacts(e.target.value), placeholder: "Jane Doe | jane@company.com" })] })] })] }), _jsxs("div", { className: "upload-card", children: [_jsxs("div", { className: "upload-card-head", children: [_jsx("span", { children: "Content" }), _jsx(HoverInfo, { text: "Upload or paste content. Preview extracts text from PDF/Excel and shows it before ingest." })] }), _jsxs("div", { className: "upload-form", children: [_jsxs("div", { className: "field dropzone", children: [_jsxs("label", { className: "dropzone-label", children: [_jsx(UploadCloud, { size: 18 }), _jsxs("div", { children: [_jsx("strong", { children: "Upload file" }), _jsx("small", { children: "Markdown, PDF, Excel" })] })] }), _jsx("input", { type: "file", accept: ".md,.markdown,.pdf,.xlsx,.xls", onChange: (e) => setFile(e.target.files ? e.target.files[0] : null) }), _jsx("div", { className: "dropzone-hint", children: file ? `Selected: ${file.name}` : 'Leave empty to paste markdown below.' })] }), _jsxs("div", { className: "field full-span", children: [_jsxs("label", { children: ["Body (Markdown) ", _jsx(HoverInfo, { text: "Required unless a file is uploaded. Keep sections concise for chunking." })] }), _jsx("textarea", { rows: 6, value: body, onChange: (e) => setBody(e.target.value), placeholder: "## Summary\\nWrite your content here...", required: !file })] })] })] })] }), _jsxs("div", { className: "upload-actions", children: [_jsx("button", { className: "secondary", type: "button", disabled: loading, onClick: (e) => handleSubmit(e, true), children: loading ? 'Validating...' : 'Preview & Validate' }), _jsx("button", { className: "primary", type: "button", disabled: loading, onClick: (e) => handleSubmit(e, false), children: loading ? 'Uploading...' : 'Upload & Index' }), status && _jsx("p", { className: "upload-status", children: status })] }), preview && (_jsxs("div", { className: "preview-panel", children: [_jsxs("div", { className: "preview-header", children: [_jsx("span", { children: "Preview" }), _jsx("small", { children: "First 1200 chars of extracted content" })] }), _jsx("pre", { children: preview })] }))] }));
}
function HoverInfo({ text }) {
    return (_jsx("span", { className: "hover-info", role: "tooltip", title: text, "aria-label": "Help", children: _jsx(Info, { size: 14 }) }));
}
