"use client";
import React, { useState, useRef, useCallback, useEffect } from "react";
import Link from "next/link";
import PocketBase from "pocketbase";
import type { Interview, EmailMessage, InterviewDate, Contact } from "@/lib/db";
import { PB_URL } from "@/lib/pb";

// ── date formatting ────────────────────────────────────────────────────────────

/** Input: "YYYY-MM-DD" or "YYYY-MM-DDTHH:MM" or ISO string. Output: "09 JUN · MON · 14:30" */
function formatDate(raw: string | null): string {
  if (!raw) return "—";
  // Parse as local time — append seconds if missing to avoid UTC shift
  const iso = raw.includes("T") ? raw : `${raw}T00:00:00`;
  const d = new Date(iso);
  if (isNaN(d.getTime())) return raw;
  const day   = String(d.getDate()).padStart(2, "0");
  const month = d.toLocaleString("en", { month: "short" }).toUpperCase();
  const dow   = d.toLocaleString("en", { weekday: "short" }).toUpperCase();
  const year  = d.getFullYear();
  const hh    = String(d.getHours()).padStart(2, "0");
  const mm    = String(d.getMinutes()).padStart(2, "0");
  const time  = `${hh}:${mm}`;
  const sameYear = year === new Date().getFullYear();
  const datePart = sameYear ? `${day} ${month} · ${dow}` : `${day} ${month} ${year} · ${dow}`;
  return `${datePart} · ${time}`;
}

/** Convert stored value to datetime-local input format "YYYY-MM-DDTHH:MM" */
function toDatetimeLocal(raw: string): string {
  if (!raw) return "";
  if (raw.includes("T")) return raw.slice(0, 16); // trim seconds/ms
  return `${raw}T00:00`;                           // date-only → midnight
}

// ── constants ──────────────────────────────────────────────────────────────────

const STATUS_OPTIONS = ["applied", "in_process", "rejected", "offer"] as const;
const ISTATUS_OPTIONS = ["scheduled", "awaiting_response"] as const;

const STATUS_COLORS: Record<string, string> = {
  applied:    "bg-indigo-800/70 text-indigo-200",
  in_process: "bg-teal-800/70 text-teal-100",
  rejected:   "bg-red-800/70 text-red-200",
  offer:      "bg-purple-700/80 text-purple-100",
};

const STATUS_LABELS: Record<string, string> = {
  applied:           "Applied",
  in_process:        "In Process",
  rejected:          "Rejected",
  offer:             "Offer",
  scheduled:         "Scheduled",
  awaiting_response: "Awaiting Feedback",
};

const ISTATUS_COLORS: Record<string, string> = {
  scheduled:         "bg-blue-700/80 text-blue-100",
  awaiting_response: "bg-amber-700/70 text-amber-100",
};

// ── helpers ────────────────────────────────────────────────────────────────────

function parseDates(raw: string | null): InterviewDate[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw) as Array<string | InterviewDate | { date?: string; label?: string; url?: string }>;
    return parsed
      .map(entry => {
        if (typeof entry === "string") return { date: entry } as InterviewDate;
        if (!entry || typeof entry !== "object") return null;
        const date = typeof entry.date === "string" ? entry.date : "";
        if (!date) return null;
        const out: InterviewDate = { date };
        if (typeof entry.label === "string" && entry.label.trim()) out.label = entry.label.trim();
        if (typeof entry.url === "string" && entry.url.trim()) out.url = entry.url.trim();
        return out;
      })
      .filter((entry): entry is InterviewDate => Boolean(entry));
  } catch {
    return [];
  }
}


function isDateFuture(d: string): boolean {
  const iso = d.includes("T") ? d : `${d}T00:00:00`;
  return new Date(iso).getTime() > Date.now();
}

function hasUpcomingDate(raw: string | null): boolean {
  return parseDates(raw).some(e => isDateFuture(e.date));
}

function parseContacts(raw: string | null): Contact[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed as Contact[] : [];
  } catch { return []; }
}

function parseEmails(raw: string | null): EmailMessage[] {
  if (!raw) return [];
  try { return JSON.parse(raw) as EmailMessage[]; } catch { return []; }
}

const STANDARD_FIELDS = ["name", "email", "telegram", "facebook"] as const;

// ── inline-editable cell ───────────────────────────────────────────────────────

interface CellProps {
  value: string;
  onSave: (v: string) => void;
  placeholder?: string;
  type?: "text" | "date" | "select";
  options?: readonly string[];
  className?: string;
  mono?: boolean;
}

function EditableCell({ value, onSave, placeholder, type = "text", options, className = "", mono }: CellProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const ref = useRef<HTMLInputElement & HTMLSelectElement>(null);

  useEffect(() => { setDraft(value); }, [value]);
  useEffect(() => { if (editing) ref.current?.focus(); }, [editing]);

  function commit() {
    setEditing(false);
    if (draft !== value) onSave(draft);
  }

  if (!editing) {
    return (
      <span
        onClick={() => { setDraft(value); setEditing(true); }}
        className={`block cursor-text rounded px-1 py-0.5 min-h-[1.4rem] hover:bg-white/5 transition-colors ${mono ? "font-data text-xs" : "text-sm"} ${className}`}
        style={{ color: value ? "var(--text-1)" : "var(--text-3)" }}
      >
        {value || placeholder || "—"}
      </span>
    );
  }

  if (type === "select" && options) {
    return (
      <select
        ref={ref as React.RefObject<HTMLSelectElement>}
        value={draft}
        onChange={e => setDraft(e.target.value)}
        onBlur={commit}
        className="text-sm rounded px-1 py-0.5 w-full outline-none"
        style={{ background: "var(--surface-hi)", border: "1px solid var(--border-hi)", color: "var(--text-1)" }}
      >
        <option value="">—</option>
        {options.map(o => <option key={o} value={o}>{STATUS_LABELS[o] ?? o}</option>)}
      </select>
    );
  }

  return (
    <input
      ref={ref as React.RefObject<HTMLInputElement>}
      type={type}
      value={draft}
      onChange={e => setDraft(e.target.value)}
      onBlur={commit}
      onKeyDown={e => { if (e.key === "Enter") commit(); if (e.key === "Escape") { setDraft(value); setEditing(false); } }}
      className={`w-full rounded px-1 py-0.5 outline-none ${mono ? "font-data text-xs" : "text-sm"}`}
      style={{ background: "var(--surface-hi)", border: "1px solid var(--border-hi)", color: "var(--text-1)" }}
    />
  );
}

// ── textarea cell (for description / comments / contacts) ──────────────────────

function EditableTextarea({ value, onSave, placeholder, rows = 3, displayClassName = "" }: { value: string; onSave: (v: string) => void; placeholder?: string; rows?: number; displayClassName?: string }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => { setDraft(value); }, [value]);
  useEffect(() => { if (editing && ref.current) { ref.current.focus(); ref.current.style.height = "auto"; ref.current.style.height = ref.current.scrollHeight + "px"; } }, [editing]);

  function commit() { setEditing(false); if (draft !== value) onSave(draft); }

  function insertNewline() {
    const el = ref.current;
    if (!el) return;
    const start = el.selectionStart ?? draft.length;
    const end = el.selectionEnd ?? draft.length;
    const next = `${draft.slice(0, start)}\n${draft.slice(end)}`;
    setDraft(next);
    queueMicrotask(() => {
      const pos = start + 1;
      el.setSelectionRange(pos, pos);
      el.style.height = "auto";
      el.style.height = el.scrollHeight + "px";
    });
  }

  if (!editing) {
    return (
      <span
        onClick={() => { setDraft(value); setEditing(true); }}
        className={`block cursor-text rounded px-1 py-0.5 min-h-[1.4rem] text-sm hover:bg-white/5 transition-colors whitespace-pre-wrap ${displayClassName}`}
        style={{ color: value ? "var(--text-1)" : "var(--text-3)" }}
      >
        {value || placeholder || "—"}
      </span>
    );
  }

  return (
    <textarea
      ref={ref}
      value={draft}
      onChange={e => { setDraft(e.target.value); e.target.style.height = "auto"; e.target.style.height = e.target.scrollHeight + "px"; }}
      onBlur={commit}
      onKeyDown={e => {
        if (e.key === "Escape") { setDraft(value); setEditing(false); }
        if (e.key === "Enter" && (e.shiftKey || e.metaKey || e.ctrlKey)) {
          e.preventDefault();
          insertNewline();
        } else if (e.key === "Enter") {
          e.preventDefault();
          commit();
        }
      }}
      rows={rows}
      className="w-full rounded px-1 py-0.5 text-sm outline-none resize-none"
      style={{ background: "var(--surface-hi)", border: "1px solid var(--border-hi)", color: "var(--text-1)" }}
    />
  );
}

// ── interview dates cell — array of {date, label?} ───────────────────────────

function InterviewDatesCell({ raw, onSave }: { raw: string | null; onSave: (json: string | null) => void }) {
  const entries = parseDates(raw);
  const [adding, setAdding] = useState(false);
  const [newDate, setNewDate] = useState("");
  const [newUrl, setNewUrl] = useState("");
  const [newLabel, setNewLabel] = useState("");

  function save(updated: InterviewDate[]) {
    onSave(updated.length ? JSON.stringify(updated) : null);
  }

  function handleAdd() {
    if (!newDate) return;
    save([
      ...entries,
      {
        date: newDate,
        ...(newUrl.trim() ? { url: newUrl.trim() } : {}),
        ...(newLabel.trim() ? { label: newLabel.trim() } : {}),
      },
    ]);
    setNewDate(""); setNewUrl(""); setNewLabel(""); setAdding(false);
  }

  function handleDelete(i: number) {
    save(entries.filter((_, idx) => idx !== i));
  }

  return (
    <div className="space-y-1 py-0.5">
      {entries.length === 0 && !adding && (
        <span className="text-xs" style={{ color: "var(--text-3)" }}>—</span>
      )}
      {entries.map((e, i) => (
        <div key={i} className="flex items-center gap-1.5 group">
          {e.url ? (
            <a
              href={e.url}
              target="_blank"
              rel="noopener noreferrer"
              className="font-data text-xs whitespace-nowrap underline underline-offset-2"
              style={{ color: isDateFuture(e.date) ? "var(--blue)" : "var(--text-3)" }}
              title={e.url}
              onClick={event => event.stopPropagation()}
            >
              {formatDate(e.date)}
            </a>
          ) : (
            <span
              className="font-data text-xs whitespace-nowrap"
              style={{ color: isDateFuture(e.date) ? "var(--blue)" : "var(--text-3)" }}
            >
              {formatDate(e.date)}
            </span>
          )}
          {e.label && (
            <span className="text-xs truncate max-w-[80px]" style={{ color: "var(--text-2)" }}>{e.label}</span>
          )}
          <button
            onClick={() => handleDelete(i)}
            className="opacity-0 group-hover:opacity-100 transition-opacity text-xs shrink-0"
            style={{ color: "var(--text-3)" }}
          >✕</button>
        </div>
      ))}

      {adding ? (
        <div className="flex flex-col gap-1 pt-1">
          <input
            type="datetime-local"
            value={newDate}
            autoFocus
            onChange={e => setNewDate(e.target.value)}
            className="w-full rounded px-1 py-0.5 font-data text-xs outline-none"
            style={{ background: "var(--surface-hi)", border: "1px solid var(--border-hi)", color: "var(--text-1)" }}
          />
          <input
            type="url"
            value={newUrl}
            onChange={e => setNewUrl(e.target.value)}
            placeholder="Calendar event URL (optional)"
            className="w-full rounded px-1 py-0.5 text-xs outline-none"
            style={{ background: "var(--surface-hi)", border: "1px solid var(--border)", color: "var(--text-1)" }}
          />
          <input
            type="text"
            value={newLabel}
            onChange={e => setNewLabel(e.target.value)}
            placeholder="Label (e.g. Technical round)"
            onKeyDown={e => { if (e.key === "Enter") handleAdd(); if (e.key === "Escape") setAdding(false); }}
            className="w-full rounded px-1 py-0.5 text-xs outline-none"
            style={{ background: "var(--surface-hi)", border: "1px solid var(--border)", color: "var(--text-1)" }}
          />
          <div className="flex gap-1">
            <button onClick={handleAdd} disabled={!newDate}
              className="text-xs px-2 py-0.5 rounded font-medium disabled:opacity-40"
              style={{ background: "var(--green-bg)", color: "var(--green)", border: "1px solid var(--green-border)" }}>✓</button>
            <button onClick={() => { setAdding(false); setNewDate(""); setNewUrl(""); setNewLabel(""); }}
              className="text-xs px-1.5 py-0.5 rounded" style={{ color: "var(--text-3)" }}>✕</button>
          </div>
        </div>
      ) : (
        <button onClick={() => setAdding(true)} className="text-xs hover:opacity-80 transition-opacity" style={{ color: "var(--text-3)" }}>+ add</button>
      )}
    </div>
  );
}

// ── link cell ─────────────────────────────────────────────────────────────────

function LinkCell({ value, onSave }: { value: string; onSave: (v: string) => void }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const ref = useRef<HTMLInputElement>(null);

  useEffect(() => { setDraft(value); }, [value]);
  useEffect(() => { if (editing) ref.current?.focus(); }, [editing]);

  function commit() { setEditing(false); if (draft !== value) onSave(draft); }

  if (!editing) {
    return (
      <div className="flex items-center gap-1 min-h-[1.4rem]">
        {value ? (
          <a
            href={value}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs underline truncate max-w-[160px] block"
            style={{ color: "var(--blue)" }}
            onClick={e => e.stopPropagation()}
          >
            {value.replace(/^https?:\/\//, "")}
          </a>
        ) : (
          <span className="text-xs" style={{ color: "var(--text-3)" }}>—</span>
        )}
        <button
          onClick={() => { setDraft(value); setEditing(true); }}
          className="shrink-0 text-[10px] ml-1 hover:opacity-80"
          style={{ color: "var(--text-3)" }}
        >✎</button>
      </div>
    );
  }

  return (
    <input
      ref={ref}
      type="url"
      value={draft}
      onChange={e => setDraft(e.target.value)}
      onBlur={commit}
      onKeyDown={e => { if (e.key === "Enter") commit(); if (e.key === "Escape") { setDraft(value); setEditing(false); } }}
      className="w-full rounded px-1 py-0.5 text-xs outline-none"
      style={{ background: "var(--surface-hi)", border: "1px solid var(--border-hi)", color: "var(--text-1)" }}
      placeholder="https://…"
    />
  );
}

// ── contacts ──────────────────────────────────────────────────────────────────

const FIELD_COLORS: Record<string, string> = {
  email:    "var(--blue)",
  telegram: "var(--teal)",
  facebook: "#818cf8",
};

function ContactsSummaryCell({ raw }: { raw: string | null }) {
  const contacts = parseContacts(raw);
  if (!contacts.length) return <span className="text-xs" style={{ color: "var(--text-3)" }}>—</span>;

  return (
    <div className="space-y-2 py-0.5">
      {contacts.map((c, i) => {
        const fields = Object.entries(c).filter(([, v]) => v);
        return (
          <div key={i} className="space-y-0.5">
            {fields.map(([k, v]) => (
              <div key={k} className="flex items-baseline gap-1.5 leading-tight">
                <span className="text-[9px] w-12 shrink-0 uppercase tracking-wider font-medium" style={{ color: "var(--text-3)" }}>{k}</span>
                <span className="text-xs truncate max-w-[140px]" style={{ color: FIELD_COLORS[k] ?? "var(--text-1)" }}>{v}</span>
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );
}

function ContactField({ label, value, onBlurSave, onDelete }: {
  label: string;
  value: string;
  onBlurSave: (v: string) => void;
  onDelete?: () => void;
}) {
  const [draft, setDraft] = useState(value);
  useEffect(() => { setDraft(value); }, [value]);
  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] w-16 shrink-0 capitalize" style={{ color: "var(--text-3)" }}>{label}</span>
      <input
        value={draft}
        onChange={e => setDraft(e.target.value)}
        onBlur={() => onBlurSave(draft)}
        onKeyDown={e => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }}
        placeholder={`${label}…`}
        className="flex-1 text-xs rounded px-1.5 py-0.5 outline-none min-w-0"
        style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-1)" }}
      />
      {onDelete && (
        <button onClick={onDelete} className="shrink-0 text-xs hover:text-red-400 transition-colors" style={{ color: "var(--text-3)" }}>✕</button>
      )}
    </div>
  );
}

function ContactCard({ contact, onUpdate, onRemoveField, onDelete }: {
  contact: Contact;
  onUpdate: (field: string, value: string) => void;
  onRemoveField: (field: string) => void;
  onDelete: () => void;
}) {
  const [addingField, setAddingField] = useState(false);
  const [newKey, setNewKey] = useState("");
  const customFields = Object.keys(contact).filter(k => !(STANDARD_FIELDS as readonly string[]).includes(k));

  function handleAddField() {
    const key = newKey.trim().toLowerCase().replace(/\s+/g, "_");
    if (!key) return;
    onUpdate(key, "");
    setNewKey(""); setAddingField(false);
  }

  return (
    <div className="rounded-lg p-3 relative space-y-1.5" style={{ background: "var(--surface-hi)", border: "1px solid var(--border)" }}>
      <button onClick={onDelete}
        className="absolute top-2 right-2 text-xs hover:text-red-400 transition-colors"
        style={{ color: "var(--text-3)" }} title="Remove contact">✕</button>
      {STANDARD_FIELDS.map(f => (
        <ContactField key={f} label={f} value={contact[f] ?? ""} onBlurSave={v => onUpdate(f, v)} />
      ))}
      {customFields.map(f => (
        <ContactField key={f} label={f} value={contact[f] ?? ""} onBlurSave={v => onUpdate(f, v)} onDelete={() => onRemoveField(f)} />
      ))}
      {addingField ? (
        <div className="flex items-center gap-2 pt-0.5">
          <input value={newKey} onChange={e => setNewKey(e.target.value)} autoFocus placeholder="field name…"
            onKeyDown={e => { if (e.key === "Enter") handleAddField(); if (e.key === "Escape") { setAddingField(false); setNewKey(""); } }}
            className="flex-1 text-xs rounded px-1.5 py-0.5 outline-none"
            style={{ background: "var(--bg)", border: "1px solid var(--border-hi)", color: "var(--text-1)" }} />
          <button onClick={handleAddField} className="text-xs px-2 py-0.5 rounded"
            style={{ background: "var(--green-bg)", color: "var(--green)", border: "1px solid var(--green-border)" }}>✓</button>
          <button onClick={() => { setAddingField(false); setNewKey(""); }} className="text-xs" style={{ color: "var(--text-3)" }}>✕</button>
        </div>
      ) : (
        <button onClick={() => setAddingField(true)} className="text-[10px] hover:opacity-80 transition-opacity pt-0.5 block"
          style={{ color: "var(--text-3)" }}>+ custom field</button>
      )}
    </div>
  );
}

function ContactsEditor({ raw, onSave }: { raw: string | null; onSave: (json: string | null) => void }) {
  const [contacts, setContacts] = useState<Contact[]>(() => parseContacts(raw));
  useEffect(() => { setContacts(parseContacts(raw)); }, [raw]);

  function save(updated: Contact[]) {
    setContacts(updated);
    onSave(updated.length ? JSON.stringify(updated) : null);
  }

  function updateField(i: number, field: string, value: string) {
    save(contacts.map((c, idx) => idx === i ? { ...c, [field]: value } : c));
  }

  function removeField(i: number, field: string) {
    save(contacts.map((c, idx) => {
      if (idx !== i) return c;
      const next = { ...c };
      delete next[field];
      return next;
    }));
  }

  return (
    <div className="space-y-3">
      {contacts.length === 0 && (
        <p className="text-xs" style={{ color: "var(--text-3)" }}>No contacts yet</p>
      )}
      {contacts.map((c, i) => (
        <ContactCard key={i} contact={c}
          onUpdate={(f, v) => updateField(i, f, v)}
          onRemoveField={f => removeField(i, f)}
          onDelete={() => save(contacts.filter((_, idx) => idx !== i))}
        />
      ))}
      <button onClick={() => save([...contacts, {}])}
        className="text-xs px-3 py-1 rounded"
        style={{ background: "var(--surface-hi)", color: "var(--text-2)", border: "1px solid var(--border)" }}>
        + Add contact
      </button>
    </div>
  );
}

// ── email thread panel ─────────────────────────────────────────────────────────

function EmailThread({ raw, onSave }: { raw: string | null; onSave: (json: string) => void }) {
  const messages = parseEmails(raw);
  const [addOpen, setAddOpen] = useState(false);
  const [newMsg, setNewMsg] = useState<EmailMessage>({ from: "", date: "", subject: "", body: "" });

  function handleAdd() {
    const updated = [...messages, newMsg];
    onSave(JSON.stringify(updated));
    setNewMsg({ from: "", date: "", subject: "", body: "" });
    setAddOpen(false);
  }

  function handleDelete(i: number) {
    const updated = messages.filter((_, idx) => idx !== i);
    onSave(updated.length ? JSON.stringify(updated) : "");
  }

  return (
    <div className="space-y-2">
      {messages.length === 0 && (
        <p className="text-xs" style={{ color: "var(--text-3)" }}>No emails</p>
      )}
      {messages.map((m, i) => (
        <div key={i} className="rounded-lg p-3 text-sm" style={{ background: "var(--surface-hi)", border: "1px solid var(--border)" }}>
          <div className="flex items-center gap-3 mb-1 text-xs" style={{ color: "var(--text-2)" }}>
            {m.from && <span>{m.from}</span>}
            {m.date && <span className="font-data">{m.date}</span>}
            {m.subject && <span className="font-medium" style={{ color: "var(--text-1)" }}>{m.subject}</span>}
            <button onClick={() => handleDelete(i)} className="ml-auto text-xs hover:text-red-400" style={{ color: "var(--text-3)" }}>✕</button>
          </div>
          <pre className="text-xs whitespace-pre-wrap" style={{ color: "var(--text-1)", fontFamily: "inherit" }}>{m.body}</pre>
        </div>
      ))}

      {addOpen ? (
        <div className="rounded-lg p-3 space-y-2" style={{ background: "var(--surface-hi)", border: "1px solid var(--border-hi)" }}>
          <div className="grid grid-cols-3 gap-2">
            {(["from", "date", "subject"] as const).map(f => (
              <input key={f} placeholder={f} value={newMsg[f] ?? ""} onChange={e => setNewMsg(m => ({ ...m, [f]: e.target.value }))}
                className="text-xs rounded px-2 py-1 outline-none" style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-1)" }} />
            ))}
          </div>
          <textarea placeholder="Body" value={newMsg.body} onChange={e => setNewMsg(m => ({ ...m, body: e.target.value }))} rows={4}
            className="w-full text-xs rounded px-2 py-1 outline-none resize-none" style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-1)" }} />
          <div className="flex gap-2">
            <button onClick={handleAdd} className="text-xs px-3 py-1 rounded" style={{ background: "var(--green-bg)", color: "var(--green)", border: "1px solid var(--green-border)" }}>Add</button>
            <button onClick={() => setAddOpen(false)} className="text-xs px-3 py-1 rounded" style={{ color: "var(--text-2)" }}>Cancel</button>
          </div>
        </div>
      ) : (
        <button onClick={() => setAddOpen(true)} className="text-xs px-2 py-1 rounded" style={{ color: "var(--text-2)", border: "1px solid var(--border)" }}>
          + Add email
        </button>
      )}
    </div>
  );
}

// ── expanded row panel ─────────────────────────────────────────────────────────

function ExpandedRow({ row, colSpan, onUpdate }: { row: Interview; colSpan: number; onUpdate: (id: string, field: string, value: string | null) => void }) {
  function save(field: string) {
    return (v: string) => onUpdate(row.id, field, v || null);
  }

  return (
    <tr>
      <td colSpan={colSpan} className="px-0 pb-0" style={{ background: "var(--bg)" }}>
        <div className="mx-4 mb-4 rounded-xl p-4 grid grid-cols-3 gap-6" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
          {/* Contacts */}
          <div className="space-y-4">
            <Section label="Contacts">
              <ContactsEditor raw={row.contacts_json} onSave={v => onUpdate(row.id, "contacts_json", v)} />
            </Section>
          </div>
          {/* Middle col */}
          <div className="space-y-4">
            <Section label="Description">
              <EditableTextarea value={row.description ?? ""} onSave={save("description")} placeholder="Add description…" />
            </Section>
            <Section label="Comments">
              <EditableTextarea value={row.comments ?? ""} onSave={save("comments")} placeholder="Add comments…" rows={2} />
            </Section>
            <Section label="Job ID (reference)">
              <EditableCell value={row.job_id ?? ""} onSave={v => onUpdate(row.id, "job_id", v ? v : null)} placeholder="optional job id" mono />
            </Section>
          </div>
          {/* Right col */}
          <div className="space-y-4">
            <Section label="Email Thread">
              <EmailThread raw={row.emails_json} onSave={save("emails_json")} />
            </Section>
          </div>
        </div>
      </td>
    </tr>
  );
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider mb-1.5 font-medium" style={{ color: "var(--text-3)" }}>{label}</div>
      {children}
    </div>
  );
}

// ── status badge ───────────────────────────────────────────────────────────────

function Badge({ value, colorMap }: { value: string | null; colorMap: Record<string, string> }) {
  if (!value) return <span style={{ color: "var(--text-3)" }}>—</span>;
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium whitespace-nowrap ${colorMap[value] ?? "bg-white/10 text-white/60"}`}>
      {STATUS_LABELS[value] ?? value}
    </span>
  );
}

// Select that shows as a badge when not editing
function SelectBadgeCell({ value, options, colorMap, onSave }: {
  value: string;
  options: readonly string[];
  colorMap: Record<string, string>;
  onSave: (v: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const ref = useRef<HTMLSelectElement>(null);
  useEffect(() => { if (editing) ref.current?.focus(); }, [editing]);

  if (!editing) {
    return (
      <span onClick={() => setEditing(true)} className="cursor-pointer block">
        <Badge value={value || null} colorMap={colorMap} />
      </span>
    );
  }
  return (
    <select
      ref={ref}
      value={value}
      onChange={e => { onSave(e.target.value); setEditing(false); }}
      onBlur={() => setEditing(false)}
      className="text-xs rounded px-1.5 py-0.5 w-full outline-none"
      style={{ background: "var(--surface-hi)", border: "1px solid var(--border-hi)", color: "var(--text-1)" }}
    >
      <option value="">—</option>
      {options.map(o => <option key={o} value={o}>{STATUS_LABELS[o] ?? o}</option>)}
    </select>
  );
}

// ── main component ─────────────────────────────────────────────────────────────

export function InterviewsClient({ interviews: initial }: { interviews: Interview[] }) {
  const [rows, setRows] = useState<Interview[]>(initial);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [saving, setSaving] = useState<Set<string>>(new Set());
  const [filterStatus, setFilterStatus] = useState<string>("");

  useEffect(() => {
    const pb = new PocketBase(PB_URL);
    pb.collection('interviews').subscribe('*', (e) => {
      if (e.action === 'create') setRows(prev => [e.record as unknown as Interview, ...prev]);
      else if (e.action === 'update') setRows(prev => prev.map(r => r.id === e.record.id ? { ...r, ...e.record } as unknown as Interview : r));
      else if (e.action === 'delete') setRows(prev => prev.filter(r => r.id !== e.record.id));
    }).catch(() => {});
    return () => { pb.collection('interviews').unsubscribe('*').catch(() => {}); };
  }, []);

  const filtered = filterStatus ? rows.filter(r => r.status === filterStatus) : rows;

  const toggleExpand = useCallback((id: string) => {
    setExpanded(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }, []);

  const patchRow = useCallback(async (id: string, field: string, value: string | null) => {
    setSaving(prev => new Set(prev).add(id));
    try {
      const res = await fetch(`/api/interviews/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ [field]: value }),
      });
      const updated = await res.json() as Interview;
      setRows(prev => prev.map(r => r.id === id ? updated : r));
    } finally {
      setSaving(prev => { const next = new Set(prev); next.delete(id); return next; });
    }
  }, []);

  async function handleNew() {
    const res = await fetch("/api/interviews", { method: "POST" });
    const created = await res.json() as Interview;
    setRows(prev => [created, ...prev]);
    setExpanded(prev => new Set(prev).add(created.id));
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this interview entry?")) return;
    await fetch(`/api/interviews/${id}`, { method: "DELETE" });
    setRows(prev => prev.filter(r => r.id !== id));
    setExpanded(prev => { const next = new Set(prev); next.delete(id); return next; });
  }

  const COLS = ["ID", "", "Company", "Job Title", "Status", "Interview Status", "Interview", "Contacts", "Job Link", "Comments", ""];

  return (
    <div className="flex flex-col w-full h-full overflow-hidden">
      {/* Top bar */}
      <div className="flex items-center gap-3 px-5 py-3 border-b shrink-0" style={{ background: "var(--surface)", borderColor: "var(--border)" }}>
        <Link href="/" className="text-xs px-2 py-1 rounded" style={{ background: "var(--surface-hi)", color: "var(--text-2)" }}>← Jobs</Link>
        <span className="text-sm font-semibold" style={{ color: "var(--text-1)" }}>Interviews</span>
        <span className="text-xs font-data" style={{ color: "var(--text-3)" }}>{filtered.length}</span>

        {/* Status filter */}
        <div className="flex gap-1 ml-4">
          {["", ...STATUS_OPTIONS].map(s => (
            <button key={s} onClick={() => setFilterStatus(s)}
              className="text-xs px-2.5 py-1 rounded transition-colors"
              style={filterStatus === s
                ? { background: "var(--surface-hi)", color: "var(--text-1)" }
                : { color: "var(--text-2)" }}>
              {s === "" ? "All" : STATUS_LABELS[s]}
            </button>
          ))}
        </div>

        <button onClick={handleNew} className="ml-auto text-xs px-3 py-1.5 rounded font-medium"
          style={{ background: "var(--green-bg)", color: "var(--green)", border: "1px solid var(--green-border)" }}>
          + New
        </button>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto">
        <table className="w-full border-collapse text-sm" style={{ minWidth: 900 }}>
          <thead>
            <tr style={{ background: "var(--surface)", borderBottom: "1px solid var(--border)" }}>
              {COLS.map((c, i) => (
                <th key={i} className="text-left px-3 py-2 text-xs font-medium whitespace-nowrap" style={{ color: "var(--text-3)" }}>{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr>
                <td colSpan={COLS.length} className="text-center py-12 text-sm" style={{ color: "var(--text-3)" }}>
                  No entries. Click <strong>+ New</strong> to add one.
                </td>
              </tr>
            )}
            {filtered.map(row => (
              <React.Fragment key={row.id}>
                <tr
                  className="border-b transition-colors hover:bg-white/[0.02]"
                  style={{
                    borderColor: hasUpcomingDate(row.interview_dates_json) ? "rgba(96,165,250,0.25)" : "var(--border)",
                    background: expanded.has(row.id)
                      ? "var(--surface)"
                      : hasUpcomingDate(row.interview_dates_json)
                        ? "rgba(96,165,250,0.06)"
                        : "transparent",
                  }}
                >
                  {/* ID */}
                  <td className="px-3 py-2 w-10 shrink-0">
                    <span className="font-data text-xs select-all" style={{ color: "var(--text-3)" }}>{row.id}</span>
                  </td>

                  {/* Expand toggle */}
                  <td className="px-3 py-2 w-8">
                    <button onClick={() => toggleExpand(row.id)}
                      className="text-xs w-5 h-5 flex items-center justify-center rounded transition-colors hover:bg-white/10"
                      style={{ color: "var(--text-3)" }}>
                      {expanded.has(row.id) ? "▼" : "▶"}
                    </button>
                  </td>

                  {/* Company */}
                  <td className="px-2 py-1.5 w-40">
                    <EditableCell value={row.company_name ?? ""} onSave={v => patchRow(row.id, "company_name", v || null)} placeholder="Company" />
                  </td>

                  {/* Job Title */}
                  <td className="px-2 py-1.5 w-52">
                    <div className="flex items-center gap-1">
                      <div className="flex-1 min-w-0">
                        <EditableCell value={row.job_title ?? ""} onSave={v => patchRow(row.id, "job_title", v || null)} placeholder="Job title" />
                      </div>
                      {row.job_url && (
                        <a href={row.job_url} target="_blank" rel="noopener noreferrer"
                          onClick={e => e.stopPropagation()}
                          className="shrink-0 text-xs leading-none hover:opacity-80"
                          style={{ color: "var(--blue)" }}
                          title={row.job_url}
                        >↗</a>
                      )}
                    </div>
                  </td>

                  {/* Status */}
                  <td className="px-2 py-1.5 w-32">
                    <SelectBadgeCell
                      value={row.status ?? ""}
                      options={STATUS_OPTIONS}
                      colorMap={STATUS_COLORS}
                      onSave={v => patchRow(row.id, "status", v || null)}
                    />
                  </td>

                  {/* Interview Status */}
                  <td className="px-2 py-1.5 w-36">
                    <SelectBadgeCell
                      value={row.interview_status ?? ""}
                      options={ISTATUS_OPTIONS}
                      colorMap={ISTATUS_COLORS}
                      onSave={v => patchRow(row.id, "interview_status", v || null)}
                    />
                  </td>

                  {/* Interview dates */}
                  <td className="px-2 py-1.5 w-52">
                    <InterviewDatesCell raw={row.interview_dates_json} onSave={v => patchRow(row.id, "interview_dates_json", v)} />
                  </td>

                  {/* Contacts */}
                  <td className="px-2 py-1.5 w-44">
                    <ContactsSummaryCell raw={row.contacts_json} />
                  </td>

                  {/* Job Link */}
                  <td className="px-2 py-1.5 w-48">
                    <LinkCell value={row.job_url ?? ""} onSave={v => patchRow(row.id, "job_url", v || null)} />
                  </td>

                  {/* Comments */}
                  <td className="px-2 py-1.5 w-56">
                    <EditableTextarea
                      value={row.comments ?? ""}
                      onSave={v => patchRow(row.id, "comments", v || null)}
                      placeholder="Comments…"
                      rows={2}
                      displayClassName="line-clamp-2"
                    />
                  </td>

                  {/* Actions */}
                  <td className="px-3 py-1.5 w-10 text-right">
                    <div className="flex items-center gap-1 justify-end">
                      {saving.has(row.id) && <span className="text-xs" style={{ color: "var(--text-3)" }}>…</span>}
                      <button onClick={() => handleDelete(row.id)} className="text-xs hover:text-red-400 transition-colors" style={{ color: "var(--text-3)" }}>✕</button>
                    </div>
                  </td>
                </tr>

                {/* Expanded panel */}
                {expanded.has(row.id) && (
                  <ExpandedRow row={row} colSpan={COLS.length} onUpdate={patchRow} />
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
