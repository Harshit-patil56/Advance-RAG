'use client';

import React, {useEffect, useMemo, useState} from 'react';
import {Loader2, Settings, XCircle} from 'lucide-react';

import {getLLMSettings, updateLLMSettings} from '@/lib/api';
import type {LLMSettings} from '@/lib/api';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

function Label({children}: {children: React.ReactNode}) {
  return (
    <label
      style={{
        display: 'block',
        fontSize: '13px',
        fontWeight: 600,
        color: 'var(--color-text-body)',
        marginBottom: '6px',
      }}
    >
      {children}
    </label>
  );
}

function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      style={{
        width: '100%',
        height: '38px',
        borderRadius: 'var(--radius-md)',
        border: '1px solid var(--color-border-base)',
        backgroundColor: 'var(--color-bg-surface)',
        color: 'var(--color-text-body)',
        padding: '0 10px',
        fontSize: '13px',
      }}
    />
  );
}

export default function SettingsModal({isOpen, onClose}: SettingsModalProps) {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<LLMSettings | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    setLoading(true);
    setError(null);
    getLLMSettings()
      .then(setForm)
      .catch(() => setError('Failed to load settings.'))
      .finally(() => setLoading(false));
  }, [isOpen]);

  const disableSave = useMemo(() => {
    if (!form) return true;
    return (!form.gemini_enabled && !form.groq_enabled) || saving;
  }, [form, saving]);

  if (!isOpen) return null;

  const setField = <K extends keyof LLMSettings>(key: K, value: LLMSettings[K]) => {
    setForm((prev) => (prev ? {...prev, [key]: value} : prev));
  };

  const submit = async () => {
    if (!form) return;
    setSaving(true);
    setError(null);
    try {
      const saved = await updateLLMSettings(form);
      setForm(saved);
      onClose();
    } catch {
      setError('Failed to save settings.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(2, 6, 23, 0.45)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1200,
        padding: '16px',
      }}
      onClick={onClose}
      aria-hidden="true"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: '100%',
          maxWidth: '680px',
          maxHeight: '85vh',
          overflowY: 'auto',
          backgroundColor: 'var(--color-bg-surface)',
          border: '1px solid var(--color-border-base)',
          borderRadius: 'var(--radius-lg)',
          boxShadow: 'var(--shadow-lg)',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderBottom: '1px solid var(--color-border-base)',
            padding: '14px 16px',
          }}
        >
          <div style={{display: 'flex', alignItems: 'center', gap: '8px'}}>
            <Settings size={18} style={{color: 'var(--color-accent)'}} aria-hidden="true" />
            <h3 style={{margin: 0, fontSize: '18px', color: 'var(--color-text-primary)', fontFamily: 'DM Sans, sans-serif'}}>Model Settings</h3>
          </div>
          <button
            onClick={onClose}
            aria-label="Close settings"
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--color-text-muted)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
            }}
          >
            <XCircle size={18} aria-hidden="true" />
          </button>
        </div>

        <div style={{padding: '16px', display: 'flex', flexDirection: 'column', gap: '16px'}}>
          {loading && (
            <div style={{display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--color-text-secondary)', fontSize: '13px'}}>
              <Loader2 size={16} className="animate-spin" aria-hidden="true" />
              Loading runtime settings...
            </div>
          )}

          {error && (
            <div
              style={{
                border: '1px solid var(--color-error-border)',
                backgroundColor: 'var(--color-error-bg)',
                color: 'var(--color-error)',
                borderRadius: 'var(--radius-md)',
                padding: '10px 12px',
                fontSize: '13px',
              }}
            >
              {error}
            </div>
          )}

          {!loading && form && (
            <>
              <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px'}}>
                <div style={{border: '1px solid var(--color-border-base)', borderRadius: 'var(--radius-md)', padding: '12px'}}>
                  <Label>Gemini</Label>
                  <label style={{display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', color: 'var(--color-text-body)', marginBottom: '10px'}}>
                    <input
                      type="checkbox"
                      checked={form.gemini_enabled}
                      onChange={(e) => setField('gemini_enabled', e.target.checked)}
                    />
                    Enabled
                  </label>
                  <Label>Model</Label>
                  <Input value={form.gemini_model} onChange={(e) => setField('gemini_model', e.target.value)} />
                </div>

                <div style={{border: '1px solid var(--color-border-base)', borderRadius: 'var(--radius-md)', padding: '12px'}}>
                  <Label>Groq</Label>
                  <label style={{display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', color: 'var(--color-text-body)', marginBottom: '10px'}}>
                    <input
                      type="checkbox"
                      checked={form.groq_enabled}
                      onChange={(e) => setField('groq_enabled', e.target.checked)}
                    />
                    Enabled
                  </label>
                  <Label>Model</Label>
                  <Input value={form.groq_model} onChange={(e) => setField('groq_model', e.target.value)} />
                </div>
              </div>

              <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px'}}>
                <div>
                  <Label>Gemini Temperature (0-2)</Label>
                  <Input
                    type="number"
                    min={0}
                    max={2}
                    step={0.1}
                    value={form.gemini_temperature}
                    onChange={(e) => setField('gemini_temperature', Number(e.target.value))}
                  />
                </div>
                <div>
                  <Label>Groq Temperature (0-2)</Label>
                  <Input
                    type="number"
                    min={0}
                    max={2}
                    step={0.1}
                    value={form.groq_temperature}
                    onChange={(e) => setField('groq_temperature', Number(e.target.value))}
                  />
                </div>
              </div>

              <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px'}}>
                <div>
                  <Label>Top P</Label>
                  <Input
                    type="number"
                    min={0.1}
                    max={1}
                    step={0.05}
                    value={form.top_p}
                    onChange={(e) => setField('top_p', Number(e.target.value))}
                  />
                </div>
                <div>
                  <Label>Gemini Max Tokens</Label>
                  <Input
                    type="number"
                    min={128}
                    max={8192}
                    step={1}
                    value={form.gemini_max_output_tokens}
                    onChange={(e) => setField('gemini_max_output_tokens', Number(e.target.value))}
                  />
                </div>
                <div>
                  <Label>Groq Max Tokens</Label>
                  <Input
                    type="number"
                    min={128}
                    max={8192}
                    step={1}
                    value={form.groq_max_tokens}
                    onChange={(e) => setField('groq_max_tokens', Number(e.target.value))}
                  />
                </div>
              </div>

              <div style={{maxWidth: '220px'}}>
                <Label>Timeout (seconds)</Label>
                <Input
                  type="number"
                  min={5}
                  max={120}
                  step={1}
                  value={form.llm_timeout_seconds}
                  onChange={(e) => setField('llm_timeout_seconds', Number(e.target.value))}
                />
              </div>

              <p style={{margin: 0, fontSize: '12px', color: 'var(--color-text-muted)'}}>
                At least one provider must remain enabled.
              </p>
            </>
          )}
        </div>

        <div
          style={{
            borderTop: '1px solid var(--color-border-base)',
            padding: '12px 16px',
            display: 'flex',
            justifyContent: 'flex-end',
            gap: '10px',
          }}
        >
          <button
            onClick={onClose}
            style={{
              height: '38px',
              minWidth: '90px',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--color-border-base)',
              backgroundColor: 'transparent',
              color: 'var(--color-text-body)',
              cursor: 'pointer',
              fontSize: '13px',
            }}
          >
            Cancel
          </button>
          <button
            onClick={submit}
            disabled={disableSave}
            style={{
              height: '38px',
              minWidth: '110px',
              borderRadius: 'var(--radius-md)',
              border: 'none',
              backgroundColor: disableSave ? 'var(--color-bg-subtle)' : 'var(--color-accent)',
              color: disableSave ? 'var(--color-text-muted)' : 'var(--color-text-inverse)',
              cursor: disableSave ? 'not-allowed' : 'pointer',
              fontSize: '13px',
              fontWeight: 500,
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
            }}
          >
            {saving ? <Loader2 size={14} className="animate-spin" aria-hidden="true" /> : null}
            {saving ? 'Saving...' : 'Save Settings'}
          </button>
        </div>
      </div>
    </div>
  );
}
