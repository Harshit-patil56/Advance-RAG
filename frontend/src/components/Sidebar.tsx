'use client';

import React from 'react';
import {
  BarChart2,
  Scale,
  MessageSquare,
  Plus,
  Pencil,
  Sheet,
  FileText,
  FileType,
  CheckSquare,
  AlertCircle,
  Loader2,
  Settings,
  Trash2,
  Globe2,
} from 'lucide-react';
import type {Session, IngestResult} from '@/lib/api';

interface SidebarProps {
  domain: 'finance' | 'law' | 'global';
  sessions: Session[];
  sessionsLoading: boolean;
  activeSessionId: string | null;
  files: IngestResult[];
  filesLoading: boolean;
  isMobile: boolean;
  isOpen: boolean;
  onCloseMobile: () => void;
  onDomainChange: (d: 'finance' | 'law' | 'global') => void;
  onSessionSelect: (id: string) => void;
  onNewSession: () => void;
  onRenameSession: (id: string, name: string) => void;
  onDeleteSession: (id: string) => void;
  onDeleteFile: (id: string) => void;
  onOpenSettings: () => void;
}

function fileIcon(filename: string) {
  const lower = filename.toLowerCase();
  if (lower.endsWith('.csv')) return <Sheet size={14} />;
  if (lower.endsWith('.pdf')) return <FileText size={14} />;
  return <FileType size={14} />;
}

function statusIcon(status: string) {
  const normalized = (status || '').toLowerCase();

  if (normalized === 'indexed')
    return <CheckSquare size={14} className="text-green-600" />;
  if (normalized === 'failed' || normalized === 'error' || normalized === 'cancelled')
    return <AlertCircle size={14} className="text-red-600" />;
  return <Loader2 size={14} className="animate-spin" style={{color: 'var(--color-text-muted)'}} />;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {month: 'short', day: 'numeric'});
}

export default function Sidebar({
  domain,
  sessions,
  sessionsLoading,
  activeSessionId,
  files,
  filesLoading,
  isMobile,
  isOpen,
  onCloseMobile,
  onDomainChange,
  onSessionSelect,
  onNewSession,
  onRenameSession,
  onDeleteSession,
  onDeleteFile,
  onOpenSettings,
}: SidebarProps) {
  const [editingSessionId, setEditingSessionId] = React.useState<string | null>(null);
  const [draftSessionName, setDraftSessionName] = React.useState('');
  const cancelRenameRef = React.useRef(false);

  const visibleSessions = sessions.filter((s) => s.domain === domain);

  return (
    <aside
      style={{
        width: '240px',
        minWidth: '240px',
        height: '100vh',
        backgroundColor: 'var(--color-bg-muted)',
        borderRight: '1px solid var(--color-border-base)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        position: isMobile ? 'fixed' : 'relative',
        left: 0,
        top: 0,
        zIndex: isMobile ? 30 : 'auto',
        transform: isMobile ? (isOpen ? 'translateX(0)' : 'translateX(-100%)') : 'none',
        transition: isMobile ? 'transform 200ms ease-in-out' : 'none',
      }}
    >
      {/* Brand */}
      <div style={{padding: '16px', borderBottom: '1px solid var(--color-border-base)'}}>
        <span
          style={{
            fontFamily: 'DM Sans, sans-serif',
            fontWeight: 700,
            fontSize: '16px',
            color: 'var(--color-accent)',
          }}
        >
          RAG Intelligence
        </span>
      </div>

      {/* Domain Selector */}
      <div style={{padding: '12px 8px', borderBottom: '1px solid var(--color-border-base)'}}>
        {(['global'] as const).map((d) => {
          const active = domain === d;
          return (
            <button
              key={d}
              onClick={() => onDomainChange(d)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                width: '100%',
                padding: '8px 10px',
                borderRadius: 'var(--radius-md)',
                border: 'none',
                cursor: 'pointer',
                backgroundColor: active ? 'var(--color-bg-accent)' : 'transparent',
                color: active ? 'var(--color-text-accent)' : 'var(--color-text-secondary)',
                fontWeight: active ? 600 : 400,
                fontSize: '14px',
                textAlign: 'left',
                transition: 'background-color 150ms ease-out',
              }}
            >
              {d === 'finance' ? (
                <BarChart2 size={18} aria-hidden="true" />
              ) : d === 'law' ? (
                <Scale size={18} aria-hidden="true" />
              ) : (
                <Globe2 size={18} aria-hidden="true" />
              )}
              {d === 'finance' ? 'Finance' : d === 'law' ? 'Law' : 'Global'}
            </button>
          );
        })}
        <div
          style={{
            height: '1px',
            backgroundColor: 'var(--color-border-base)',
            margin: '8px 10px',
          }}
        />
        {(['finance', 'law'] as const).map((d) => {
          const active = domain === d;
          return (
            <button
              key={d}
              onClick={() => onDomainChange(d)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                width: '100%',
                padding: '8px 10px',
                borderRadius: 'var(--radius-md)',
                border: 'none',
                cursor: 'pointer',
                backgroundColor: active ? 'var(--color-bg-accent)' : 'transparent',
                color: active ? 'var(--color-text-accent)' : 'var(--color-text-secondary)',
                fontWeight: active ? 600 : 400,
                fontSize: '14px',
                textAlign: 'left',
                transition: 'background-color 150ms ease-out',
              }}
            >
              {d === 'finance' ? <BarChart2 size={18} aria-hidden="true" /> : <Scale size={18} aria-hidden="true" />}
              {d === 'finance' ? 'Finance' : 'Law'}
            </button>
          );
        })}
      </div>

      {/* Sessions */}
      <div style={{flex: 1, overflowY: 'auto', padding: '8px'}}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '8px 8px 4px',
          }}
        >
          <span
            style={{
              fontSize: '11px',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              color: 'var(--color-text-muted)',
              fontWeight: 500,
            }}
          >
            Sessions
          </span>
          <button
            onClick={onNewSession}
            aria-label="New session"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '24px',
              height: '24px',
              borderRadius: 'var(--radius-sm)',
              border: 'none',
              backgroundColor: 'transparent',
              color: 'var(--color-text-muted)',
              cursor: 'pointer',
            }}
          >
            <Plus size={14} />
          </button>
        </div>

        {sessionsLoading && (
          <div style={{display: 'flex', flexDirection: 'column', gap: '8px', padding: '8px 6px 4px'}}>
            {[1, 2, 3, 4].map((row) => (
              <div
                key={`session-skeleton-${row}`}
                className="shimmer"
                style={{height: '30px', borderRadius: 'var(--radius-md)', opacity: 0.55}}
              />
            ))}
          </div>
        )}

        {!sessionsLoading && visibleSessions.length === 0 && (
          <p style={{padding: '8px', fontSize: '13px', color: 'var(--color-text-muted)'}}>
            No sessions yet
          </p>
        )}

        {!sessionsLoading && visibleSessions.map((s) => {
          const active = s.session_id === activeSessionId;
          const isEditing = editingSessionId === s.session_id;
          const fallbackLabel = `${formatDate(s.created_at)} · ${s.domain}`;
          const label = s.session_name?.trim() ? s.session_name : fallbackLabel;
          return (
            <div
              key={s.session_id}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '8px 10px',
                borderRadius: 'var(--radius-md)',
                borderLeft: active ? '3px solid var(--color-accent)' : '3px solid transparent',
                backgroundColor: active ? 'var(--color-bg-subtle)' : 'transparent',
                cursor: 'pointer',
                marginBottom: '2px',
              }}
              onClick={() => onSessionSelect(s.session_id)}
            >
              <MessageSquare size={14} aria-hidden="true" style={{flexShrink: 0, color: 'var(--color-text-muted)'}} />
              {isEditing ? (
                <input
                  autoFocus
                  value={draftSessionName}
                  onChange={(e) => setDraftSessionName(e.target.value)}
                  onClick={(e) => e.stopPropagation()}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      // Submit once through onBlur for consistent behavior.
                      e.currentTarget.blur();
                    }
                    if (e.key === 'Escape') {
                      cancelRenameRef.current = true;
                      setEditingSessionId(null);
                    }
                  }}
                  onBlur={() => {
                    if (cancelRenameRef.current) {
                      cancelRenameRef.current = false;
                      return;
                    }
                    const next = draftSessionName.trim();
                    if (next) onRenameSession(s.session_id, next);
                    setEditingSessionId(null);
                  }}
                  style={{
                    flex: 1,
                    fontSize: '13px',
                    color: 'var(--color-text-body)',
                    backgroundColor: 'var(--color-bg-surface)',
                    border: '1px solid var(--color-border-base)',
                    borderRadius: '6px',
                    padding: '4px 6px',
                    minWidth: 0,
                  }}
                />
              ) : (
                <span
                  style={{
                    flex: 1,
                    fontSize: '13px',
                    color: active ? 'var(--color-text-accent)' : 'var(--color-text-body)',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {label}
                </span>
              )}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setEditingSessionId(s.session_id);
                  setDraftSessionName(label);
                }}
                aria-label="Rename session"
                style={{
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  color: 'var(--color-text-muted)',
                  padding: '2px',
                  display: 'flex',
                  alignItems: 'center',
                }}
                title="Rename session"
              >
                <Pencil size={12} />
              </button>
              <button
                onClick={(e) => {e.stopPropagation(); onDeleteSession(s.session_id);}}
                aria-label="Delete session"
                style={{
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  color: 'var(--color-text-muted)',
                  padding: '2px',
                  display: 'flex',
                  alignItems: 'center',
                }}
              >
                <Trash2 size={12} />
              </button>
            </div>
          );
        })}

        {/* Files */}
        {(filesLoading || files.length > 0) && (
          <>
            <div style={{padding: '12px 8px 4px'}}>
              <span
                style={{
                  fontSize: '11px',
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                  color: 'var(--color-text-muted)',
                  fontWeight: 500,
                }}
              >
                Files
              </span>
            </div>
            {filesLoading && (
              <div style={{display: 'flex', flexDirection: 'column', gap: '8px', padding: '4px 10px 8px'}}>
                {[1, 2, 3].map((row) => (
                  <div
                    key={`file-skeleton-${row}`}
                    className="shimmer"
                    style={{height: '22px', borderRadius: 'var(--radius-sm)', opacity: 0.55}}
                  />
                ))}
              </div>
            )}
            {!filesLoading && files.map((f) => (
              <div
                key={f.file_id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '6px 10px',
                  fontSize: '12px',
                  color: 'var(--color-text-secondary)',
                }}
              >
                <span style={{color: 'var(--color-text-muted)'}}>{fileIcon(f.filename)}</span>
                <span style={{flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'}}>
                  {f.filename}
                </span>
                {statusIcon(f.status)}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteFile(f.file_id);
                  }}
                  aria-label="Delete file"
                  style={{
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    color: 'var(--color-text-muted)',
                    padding: '2px',
                    display: 'flex',
                    alignItems: 'center',
                    marginLeft: '4px'
                  }}
                  title="Delete file"
                >
                  <Trash2 size={12} />
                </button>
              </div>
            ))}
          </>
        )}
      </div>

      {/* Bottom Settings */}
      <div style={{padding: '12px 16px', borderTop: '1px solid var(--color-border-base)'}}>
        <button
          onClick={() => {
            onOpenSettings();
            if (isMobile) onCloseMobile();
          }}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            color: 'var(--color-text-muted)',
            fontSize: '13px',
          }}
        >
          <Settings size={16} aria-hidden="true" />
          Settings
        </button>
      </div>
    </aside>
  );
}
