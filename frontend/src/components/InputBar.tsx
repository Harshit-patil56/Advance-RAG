'use client';

/**
 * InputBar — fixed bottom input area (ui.md Section 10.2).
 * 72px min height, send button + file attach.
 */

import React, {useRef, useState} from 'react';
import {Send, Paperclip, Loader2} from 'lucide-react';

interface InputBarProps {
  disabled: boolean;
  loading: boolean;
  accept?: string;
  onSubmit: (query: string) => void;
  onFileSelect: (file: File) => void;
}

export default function InputBar({disabled, loading, accept = '.csv,.pdf,.txt', onSubmit, onFileSelect}: InputBarProps) {
  const [query, setQuery] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);

  const handleSubmit = () => {
    const trimmed = query.trim();
    if (!trimmed || disabled || loading) return;
    onSubmit(trimmed);
    setQuery('');
  };

  const handleKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div
      style={{
        minHeight: '84px',
        borderTop: '1px solid var(--color-border-base)',
        backgroundColor: 'var(--color-bg-page)',
        padding: '12px 24px 16px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '920px',
          display: 'flex',
          alignItems: 'flex-end',
          gap: '8px',
          backgroundColor: 'var(--color-bg-surface)',
          border: '1px solid var(--color-border-base)',
          borderRadius: '16px',
          padding: '8px',
          boxShadow: 'var(--shadow-sm)',
        }}
      >
      {/* Hidden file input */}
      <input
        ref={fileRef}
        type="file"
        accept={accept}
        style={{display: 'none'}}
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) {
            onFileSelect(f);
            e.target.value = '';
          }
        }}
      />

      {/* File attach button */}
      <button
        onClick={() => fileRef.current?.click()}
        disabled={disabled}
        aria-label="Attach file"
        style={{
          width: '40px',
          height: '40px',
          minWidth: '40px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderRadius: '12px',
          border: 'none',
          backgroundColor: 'transparent',
          color: disabled ? 'var(--color-text-disabled)' : 'var(--color-text-secondary)',
          cursor: disabled ? 'not-allowed' : 'pointer',
          flexShrink: 0,
          transition: 'background-color 150ms ease-out',
        }}
      >
        <Paperclip size={16} aria-hidden="true" />
      </button>

      {/* Query textarea */}
      <textarea
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={handleKey}
        disabled={disabled || loading}
        placeholder={disabled ? 'Upload a file to start querying' : 'Ask a question about your document…'}
        rows={1}
        style={{
          flex: 1,
          resize: 'none',
          border: 'none',
          borderRadius: '12px',
          padding: '10px 12px',
          fontSize: '14px',
          fontFamily: 'Inter, sans-serif',
          color: 'var(--color-text-body)',
          backgroundColor: 'transparent',
          outline: 'none',
          lineHeight: 1.5,
          minHeight: '40px',
        }}
      />

      {/* Send button */}
      <button
        onClick={handleSubmit}
        disabled={disabled || loading || !query.trim()}
        aria-label="Send message"
        style={{
          width: '40px',
          height: '40px',
          minWidth: '40px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderRadius: '12px',
          border: 'none',
          backgroundColor:
            disabled || loading || !query.trim()
              ? 'var(--color-bg-subtle)'
              : 'var(--color-accent)',
          color:
            disabled || loading || !query.trim()
              ? 'var(--color-text-disabled)'
              : 'var(--color-text-inverse)',
          cursor: disabled || loading || !query.trim() ? 'not-allowed' : 'pointer',
          flexShrink: 0,
          transition: 'background-color 150ms ease-out',
        }}
      >
        {loading ? (
          <Loader2 size={16} className="animate-spin" aria-hidden="true" />
        ) : (
          <Send size={16} aria-hidden="true" />
        )}
      </button>
      </div>
    </div>
  );
}
