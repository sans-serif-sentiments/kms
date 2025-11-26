import { useState } from 'react';
import { Info, UploadCloud } from 'lucide-react';
import { uploadDoc, uploadFile, type UploadPayload } from '../lib/api';

type Props = {
  onSuccess?: (path: string) => void;
};

export function UploadPanel({ onSuccess }: Props) {
  const [id, setId] = useState('');
  const [title, setTitle] = useState('');
  const [category, setCategory] = useState('faq');
  const [body, setBody] = useState('');
  const [contacts, setContacts] = useState('');
  const [tags, setTags] = useState('');
  const [status, setStatus] = useState<string | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const contactTemplates = [
    { label: 'LangGraph Docs Steward', line: 'LangGraph Docs Steward | langgraph-docs@company.com' },
    { label: 'Knowledge Steward', line: 'Knowledge Steward | knowledge@company.com' },
    { label: 'Compliance', line: 'Compliance Program Manager | compliance@company.com' },
  ];

  const handleSubmit = async (e: React.FormEvent, dryRun = false) => {
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
      } else {
        const payload: UploadPayload = {
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
      } else {
        setStatus(`Uploaded to ${pathDisplay} (indexed ${res.indexed}, chunks ${res.chunks})`);
        if (onSuccess) onSuccess(res.path || pathDisplay);
        setId('');
        setTitle('');
        setBody('');
        setContacts('');
        setTags('');
        setFile(null);
      }
    } catch (err) {
      setStatus(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card upload-panel">
      <div className="upload-header">
        <div>
          <p className="badge">Beta</p>
          <h2>Quick KB Upload</h2>
          <p className="upload-hint">
            Add docs with required metadata. Use Preview to normalize PDFs/Excel before ingest.
          </p>
        </div>
      </div>
      <div className="upload-sections">
        <div className="upload-card">
          <div className="upload-card-head">
            <span>Metadata</span>
            <HoverInfo text="ID must follow KB naming (e.g., LG-XXX). Title and category are required." />
          </div>
          <div className="upload-form" onSubmit={(e) => handleSubmit(e, false)}>
            <div className="field">
              <label>
                KB ID <HoverInfo text="Use prefixes like LG-, HR-, FIN-. Avoid spaces." />
              </label>
              <input value={id} onChange={(e) => setId(e.target.value)} placeholder="LG-NEW-DOC" required />
            </div>
            <div className="field">
              <label>
                Title <HoverInfo text="Human-readable doc title." />
              </label>
              <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Doc title" required />
            </div>
            <div className="field">
              <label>
                Category <HoverInfo text="Must match allowed categories (faq, process, policy, concept, langraph, pattern)." />
              </label>
              <select value={category} onChange={(e) => setCategory(e.target.value)}>
                <option value="faq">faq</option>
                <option value="process">process</option>
                <option value="policy">policy</option>
                <option value="concept">concept</option>
                <option value="langraph">langraph</option>
                <option value="pattern">pattern</option>
              </select>
            </div>
            <div className="field">
              <label>
                Tags <HoverInfo text="Comma-separated tags to improve retrieval." />
              </label>
              <input value={tags} onChange={(e) => setTags(e.target.value)} placeholder="langgraph, ingestion" />
            </div>
          </div>
        </div>
        <div className="upload-card">
          <div className="upload-card-head">
            <span>Ownership</span>
            <HoverInfo text="Contacts are required. Pick a template or add one per line: name | email." />
          </div>
          <div className="upload-form">
            <div className="field">
              <label>Contact templates</label>
              <select
                onChange={(e) => {
                  if (!e.target.value) return;
                  setContacts((prev) => (prev ? `${prev}\n${e.target.value}` : e.target.value));
                  e.target.selectedIndex = 0;
                }}
              >
                <option value="">Select a template</option>
                {contactTemplates.map((tpl) => (
                  <option key={tpl.label} value={tpl.line}>
                    {tpl.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="field full-span">
              <label>
                Contacts <HoverInfo text="One per line: name | email. Required for ingestion." />
              </label>
              <textarea
                rows={3}
                value={contacts}
                onChange={(e) => setContacts(e.target.value)}
                placeholder="Jane Doe | jane@company.com"
              />
            </div>
          </div>
        </div>
        <div className="upload-card">
          <div className="upload-card-head">
            <span>Content</span>
            <HoverInfo text="Upload or paste content. Preview extracts text from PDF/Excel and shows it before ingest." />
          </div>
          <div className="upload-form">
            <div className="field dropzone">
              <label className="dropzone-label">
                <UploadCloud size={18} />
                <div>
                  <strong>Upload file</strong>
                  <small>Markdown, PDF, Excel</small>
                </div>
              </label>
              <input
                type="file"
                accept=".md,.markdown,.pdf,.xlsx,.xls"
                onChange={(e) => setFile(e.target.files ? e.target.files[0] : null)}
              />
              <div className="dropzone-hint">
                {file ? `Selected: ${file.name}` : 'Leave empty to paste markdown below.'}
              </div>
            </div>
            <div className="field full-span">
              <label>
                Body (Markdown) <HoverInfo text="Required unless a file is uploaded. Keep sections concise for chunking." />
              </label>
              <textarea
                rows={6}
                value={body}
                onChange={(e) => setBody(e.target.value)}
                placeholder="## Summary\nWrite your content here..."
                required={!file}
              />
            </div>
          </div>
        </div>
      </div>
      <div className="upload-actions">
        <button
          className="secondary"
          type="button"
          disabled={loading}
          onClick={(e) => handleSubmit(e as unknown as React.FormEvent, true)}
        >
          {loading ? 'Validating...' : 'Preview & Validate'}
        </button>
        <button className="primary" type="button" disabled={loading} onClick={(e) => handleSubmit(e as unknown as React.FormEvent, false)}>
          {loading ? 'Uploading...' : 'Upload & Index'}
        </button>
        {status && <p className="upload-status">{status}</p>}
      </div>
      {preview && (
        <div className="preview-panel">
          <div className="preview-header">
            <span>Preview</span>
            <small>First 1200 chars of extracted content</small>
          </div>
          <pre>{preview}</pre>
        </div>
      )}
    </div>
  );
}

function HoverInfo({ text }: { text: string }) {
  return (
    <span className="hover-info" role="tooltip" title={text} aria-label="Help">
      <Info size={14} />
    </span>
  );
}
