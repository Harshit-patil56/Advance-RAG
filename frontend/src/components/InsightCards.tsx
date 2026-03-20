'use client';

/**
 * InsightCards — renders structured LLM response from the backend.
 * Maps to ui.md Section 9.1 (Insight Card pattern).
 * Animations: ui.md Section 16.6 (card entrance, staggered, 200ms, ease-out).
 */

import React from 'react';
import {motion} from 'framer-motion';
import {AlertTriangle, ShieldAlert, BookOpen, Sparkles, Zap, Search, ChevronDown} from 'lucide-react';
import type {LLMResponse} from '@/lib/api';

interface InsightCardsProps {
  response: LLMResponse;
  llmProvider: string;
  retrievalScoreAvg: number;
  retrievalConfidence?: 'insufficient' | 'low' | 'normal' | 'unknown';
  latencyMs: number;
}

interface ToolStep {
  tool: string;
  args?: Record<string, unknown>;
  status?: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

function parseToolSteps(data: Record<string, unknown>): ToolStep[] {
  const raw = data.tool_steps ?? data.steps ?? data.tool_calls;
  if (!Array.isArray(raw)) return [];

  const parsed: ToolStep[] = [];
  for (const item of raw) {
    if (!isRecord(item)) continue;
    const tool = typeof item.tool === 'string'
      ? item.tool
      : typeof item.name === 'string'
        ? item.name
        : typeof item.action === 'string'
          ? item.action
          : '';
    if (!tool) continue;

    parsed.push({
      tool,
      args: isRecord(item.args)
        ? item.args
        : isRecord(item.arguments)
          ? item.arguments
          : undefined,
      status: typeof item.status === 'string' ? item.status : undefined,
    });
  }
  return parsed;
}

function extractNarrativeText(response: LLMResponse): string | null {
  const data = isRecord(response.data) ? response.data : {};
  const preferred = ['answer', 'text', 'content', 'message', 'raw_answer', 'summary'];
  for (const key of preferred) {
    const val = data[key];
    if (typeof val === 'string' && val.trim()) return val.trim();
  }

  if (response.insights.length === 1) {
    const single = response.insights[0]?.trim() ?? '';
    if (single.includes('\n') || single.includes('```')) return single;
  }

  return null;
}

function renderInlineCode(line: string): React.ReactNode[] {
  const parts = line.split(/(`[^`]+`)/g);
  return parts.map((part, idx) => {
    if (part.startsWith('`') && part.endsWith('`') && part.length >= 2) {
      const codeText = part.slice(1, -1);
      return (
        <code
          key={idx}
          style={{
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: '12px',
            backgroundColor: 'var(--color-bg-page)',
            border: '1px solid var(--color-border-base)',
            borderRadius: '6px',
            padding: '1px 5px',
            color: 'var(--color-text-secondary)',
          }}
        >
          {codeText}
        </code>
      );
    }
    return <React.Fragment key={idx}>{part}</React.Fragment>;
  });
}

function RichNarrativeCard({text}: {text: string}) {
  const lines = text.split('\n');
  const nodes: React.ReactNode[] = [];
  let codeBuffer: string[] = [];
  let inFence = false;
  let key = 0;

  const flushCode = () => {
    if (!codeBuffer.length) return;
    nodes.push(
      <pre
        key={`code-${key++}`}
        style={{
          margin: '12px 0',
          padding: '14px',
          borderRadius: '12px',
          backgroundColor: 'var(--color-bg-page)',
          border: '1px solid var(--color-border-base)',
          color: 'var(--color-text-primary)',
          fontFamily: 'JetBrains Mono, monospace',
          fontSize: '12px',
          lineHeight: 1.55,
          overflowX: 'auto',
          whiteSpace: 'pre-wrap',
        }}
      >
        {codeBuffer.join('\n')}
      </pre>,
    );
    codeBuffer = [];
  };

  for (const line of lines) {
    if (line.trimStart().startsWith('```')) {
      if (inFence) {
        inFence = false;
        flushCode();
      } else {
        inFence = true;
      }
      continue;
    }

    if (inFence) {
      codeBuffer.push(line);
      continue;
    }

    if (!line.trim()) {
      nodes.push(<div key={`sp-${key++}`} style={{height: '10px'}} />);
      continue;
    }

    nodes.push(
      <p
        key={`p-${key++}`}
        style={{
          margin: 0,
          fontSize: '15px',
          lineHeight: 1.75,
          color: 'var(--color-text-body)',
        }}
      >
        {renderInlineCode(line)}
      </p>,
    );
  }

  flushCode();

  return (
    <motion.div
      variants={cardVariants}
      initial="hidden"
      animate="visible"
      style={{
        backgroundColor: 'var(--color-bg-surface)',
        border: '1px solid var(--color-border-base)',
        borderRadius: 'var(--radius-lg)',
        boxShadow: 'var(--shadow-sm)',
        padding: '18px',
        marginBottom: '12px',
      }}
    >
      <div style={{display: 'flex', flexDirection: 'column', gap: '2px'}}>{nodes}</div>
    </motion.div>
  );
}

function ToolStepsCard({steps}: {steps: ToolStep[]}) {
  const [open, setOpen] = React.useState(true);
  if (steps.length === 0) return null;

  return (
    <motion.div
      variants={cardVariants}
      initial="hidden"
      animate="visible"
      style={{
        backgroundColor: 'var(--color-bg-surface)',
        border: '1px solid var(--color-border-base)',
        borderRadius: 'var(--radius-lg)',
        boxShadow: 'var(--shadow-sm)',
        marginBottom: '12px',
        overflow: 'hidden',
      }}
    >
      <button
        onClick={() => setOpen((v) => !v)}
        style={{
          width: '100%',
          border: 'none',
          backgroundColor: 'transparent',
          padding: '12px 14px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          cursor: 'pointer',
        }}
      >
        <span style={{display: 'inline-flex', alignItems: 'center', gap: '8px', color: 'var(--color-text-secondary)', fontSize: '13px'}}>
          <ChevronDown size={14} style={{transform: open ? 'rotate(0deg)' : 'rotate(-90deg)', transition: 'transform 120ms ease'}} />
          {open ? 'Hide steps' : 'Show steps'}
        </span>
        <span
          style={{
            fontSize: '11px',
            fontWeight: 600,
            color: 'var(--color-success)',
            backgroundColor: 'var(--color-success-bg)',
            border: '1px solid var(--color-success-border)',
            padding: '2px 8px',
            borderRadius: '999px',
          }}
        >
          {steps.length} step{steps.length > 1 ? 's' : ''} completed
        </span>
      </button>

      {open && (
        <div style={{padding: '0 14px 12px'}}>
          {steps.map((step, idx) => (
            <div
              key={`${step.tool}-${idx}`}
              style={{
                border: '1px solid var(--color-border-base)',
                backgroundColor: 'var(--color-bg-page)',
                borderRadius: '10px',
                padding: '10px 12px',
                marginBottom: idx === steps.length - 1 ? 0 : '8px',
              }}
            >
              <div style={{display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px'}}>
                <span style={{display: 'inline-flex', alignItems: 'center', gap: '8px', color: 'var(--color-text-primary)', fontSize: '13px', fontWeight: 600}}>
                  <Search size={13} />
                  {step.tool}
                </span>
                <span style={{fontSize: '11px', color: 'var(--color-text-muted)'}}>
                  {step.status ?? 'Complete'}
                </span>
              </div>
              {step.args && Object.keys(step.args).length > 0 && (
                <pre
                  style={{
                    margin: '8px 0 0',
                    padding: '8px',
                    borderRadius: '8px',
                    backgroundColor: 'var(--color-bg-muted)',
                    border: '1px solid var(--color-border-base)',
                    color: 'var(--color-text-secondary)',
                    fontFamily: 'JetBrains Mono, monospace',
                    fontSize: '11px',
                    lineHeight: 1.45,
                    overflowX: 'auto',
                  }}
                >
                  {JSON.stringify(step.args, null, 2)}
                </pre>
              )}
            </div>
          ))}
        </div>
      )}
    </motion.div>
  );
}

function normalizeDisplayItem(raw: string): string {
  const text = (raw ?? '').trim();
  if (!text) return '';

  // Handle legacy payloads where backend stored object entries as JSON strings.
  if (text.startsWith('{') && text.endsWith('}')) {
    try {
      const parsed = JSON.parse(text) as Record<string, unknown>;
      const preferredKeys = ['description', 'text', 'message', 'summary', 'recommendation', 'insight', 'warning'];
      for (const key of preferredKeys) {
        const value = parsed[key];
        if (typeof value === 'string' && value.trim()) {
          return value.trim();
        }
      }

      for (const value of Object.values(parsed)) {
        if (typeof value === 'string' && value.trim()) return value.trim();
        if (typeof value === 'number' || typeof value === 'boolean') return String(value);
      }
    } catch {
      // Not valid JSON object string; keep original text.
    }
  }

  return text;
}

function normalizeItems(items: string[]): string[] {
  const out: string[] = [];
  const seen = new Set<string>();

  for (const item of items || []) {
    const normalized = normalizeDisplayItem(item);
    if (!normalized) continue;
    const key = normalized.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(normalized);
  }

  return out;
}

/* Animation variants (ui.md Section 16.6 — 200ms ease-out, translateY 8px) */
const cardVariants = {
  hidden: {opacity: 0, y: 8},
  visible: {opacity: 1, y: 0, transition: {duration: 0.2, ease: 'easeOut' as const}},
};

const staggerContainer = {
  hidden: {},
  visible: {transition: {staggerChildren: 0.07}},
};

function StructuredResponseCard({
  insights,
  warnings,
  recommendations,
}: {
  insights: string[];
  warnings: string[];
  recommendations: string[];
}) {
  if (insights.length === 0 && warnings.length === 0 && recommendations.length === 0) {
    return null;
  }

  return (
    <motion.div
      variants={cardVariants}
      initial="hidden"
      animate="visible"
      style={{
        backgroundColor: 'var(--color-bg-page)',
        border: '1px solid var(--color-border-base)',
        borderRadius: '12px',
        padding: '14px',
        marginBottom: '10px',
      }}
    >
      {insights.length > 0 && (
        <div style={{display: 'flex', flexDirection: 'column', gap: '10px'}}>
          {insights.map((item, idx) => (
            <p
              key={`ins-${idx}`}
              style={{
                color: 'var(--color-text-body)',
                fontSize: '15px',
                lineHeight: 1.65,
                margin: 0,
              }}
            >
              {item}
            </p>
          ))}
        </div>
      )}

      {warnings.length > 0 && (
        <div style={{marginTop: insights.length > 0 ? '12px' : 0, display: 'flex', flexWrap: 'wrap', gap: '8px'}}>
          {warnings.map((warning, idx) => (
            <span
              key={`warn-${idx}`}
              style={{
                fontSize: '12px',
                color: 'var(--color-warning)',
                backgroundColor: 'var(--color-warning-bg)',
                border: '1px solid var(--color-warning-border)',
                borderRadius: '12px',
                padding: '3px 10px',
              }}
            >
              {warning}
            </span>
          ))}
        </div>
      )}

      {recommendations.length > 0 && (
        <div style={{marginTop: warnings.length > 0 || insights.length > 0 ? '12px' : 0}}>
          {recommendations.map((rec, idx) => (
            <p
              key={`rec-${idx}`}
              style={{
                margin: idx === 0 ? 0 : '6px 0 0',
                fontSize: '13px',
                color: 'var(--color-text-secondary)',
                lineHeight: 1.5,
              }}
            >
              {rec}
            </p>
          ))}
        </div>
      )}
    </motion.div>
  );
}

function LawDataSection({data}: {data: Record<string, unknown>}) {
  if (!data || Object.keys(data).length === 0) return null;

  const clauses = data['clauses'] as {name: string; description?: string}[] | undefined;
  const risks = data['risks'] as {level: string; description: string}[] | undefined;

  return (
    <>
      {clauses && clauses.length > 0 && (
        <div
          style={{
            backgroundColor: 'var(--color-bg-surface)',
            border: '1px solid var(--color-border-base)',
            borderLeft: '3px solid var(--color-text-secondary)',
            borderRadius: 'var(--radius-md)',
            boxShadow: 'var(--shadow-sm)',
            padding: '16px',
            marginBottom: '8px',
          }}
        >
          <div style={{display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px'}}>
            <BookOpen size={16} aria-hidden="true" style={{color: 'var(--color-text-secondary)'}} />
            <span style={{fontFamily: 'DM Sans, sans-serif', fontWeight: 600, fontSize: '13px', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--color-text-primary)'}}>
              Clauses
            </span>
          </div>
          {clauses.map((c, i) => {
            const name = (c.name || '').trim();
            const description = (c.description || '').trim();
            if (!description) {
              return (
                <div key={i} style={{marginBottom: '8px', fontSize: '14px', color: 'var(--color-text-body)', lineHeight: 1.5}}>
                  {name}
                </div>
              );
            }
            return (
              <div key={i} style={{marginBottom: '8px', fontSize: '14px', color: 'var(--color-text-body)', lineHeight: 1.5}}>
                <strong>{name}</strong>{` - ${description}`}
              </div>
            );
          })}
        </div>
      )}

      {risks && risks.map((r, i) => {
        const isHigh = r.level?.toLowerCase() === 'high';
        const isMed = r.level?.toLowerCase() === 'medium' || r.level?.toLowerCase() === 'med';
        const icon = isHigh ? (
          <ShieldAlert size={14} style={{color: 'var(--color-error)'}} />
        ) : isMed ? (
          <AlertTriangle size={14} style={{color: 'var(--color-warning)'}} />
        ) : null;

        return (
          <div
            key={i}
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: '8px',
              padding: '8px 12px',
              marginBottom: '4px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: isHigh ? 'var(--color-error-bg)' : isMed ? 'var(--color-warning-bg)' : 'var(--color-success-bg)',
              border: `1px solid ${isHigh ? 'var(--color-error-border)' : isMed ? 'var(--color-warning-border)' : 'var(--color-success-border)'}`,
              fontSize: '13px',
            }}
          >
            {icon}
            <span>{r.description}</span>
          </div>
        );
      })}
    </>
  );
}

export default function InsightCards({response, llmProvider, retrievalScoreAvg, retrievalConfidence = 'unknown', latencyMs}: InsightCardsProps) {
  const normalizedInsights = normalizeItems(response.insights || []);
  const normalizedWarnings = normalizeItems(response.warnings || []);
  const normalizedRecommendations = normalizeItems(response.recommendations || []);
  const responseData = isRecord(response.data) ? response.data : {};
  const toolSteps = parseToolSteps(responseData);
  const narrativeText = extractNarrativeText(response);
  const scorePct = Number.isFinite(retrievalScoreAvg)
    ? Math.max(0, Math.min(100, Math.round(retrievalScoreAvg * 100)))
    : 0;

  const providerKey = (llmProvider || '').toLowerCase();
  const providerLabel =
    providerKey === 'gemini' ? 'Gemini' :
    providerKey === 'groq' ? 'Groq' :
    'No LLM';
  const providerBg =
    providerKey === 'gemini' ? 'var(--color-accent-subtle)' :
    providerKey === 'groq' ? 'var(--color-bg-muted)' :
    'var(--color-bg-muted)';
  const providerColor =
    providerKey === 'gemini' ? 'var(--color-text-accent)' :
    providerKey === 'groq' ? 'var(--color-text-primary)' :
    'var(--color-text-muted)';

  if (!response) {
    return (
      <div style={{ color: 'var(--color-error)', padding: '16px', backgroundColor: 'var(--color-error-bg)', borderRadius: 'var(--radius-md)', border: '1px solid var(--color-error-border)' }}>
        Failed to parse structured insights from the assistant&apos;s previous response.
      </div>
    );
  }

  return (
    <motion.div
      variants={staggerContainer}
      initial="hidden"
      animate="visible"
      style={{width: '100%'}}
    >
      <ToolStepsCard steps={toolSteps} />

      {narrativeText ? (
        <RichNarrativeCard text={narrativeText} />
      ) : (
        <StructuredResponseCard
          insights={normalizedInsights}
          warnings={normalizedWarnings}
          recommendations={normalizedRecommendations}
        />
      )}
      {response.data && Object.keys(response.data).length > 0 && (
        <LawDataSection data={response.data} />
      )}

      {/* LLM Provider badge + metadata — fades in last */}
      <motion.div
        variants={cardVariants}
        style={{display: 'flex', alignItems: 'center', gap: '12px', marginTop: '8px', flexWrap: 'wrap', paddingLeft: '2px'}}
      >
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '4px',
            padding: '3px 8px',
            borderRadius: 'var(--radius-full)',
            fontSize: '11px',
            fontWeight: 500,
            backgroundColor: providerBg,
            color: providerColor,
            border: '1px solid var(--color-border-base)',
          }}
        >
          {providerKey === 'gemini' ? (
            <Sparkles size={10} aria-hidden="true" />
          ) : providerKey === 'groq' ? (
            <Zap size={10} aria-hidden="true" />
          ) : (
            <AlertTriangle size={10} aria-hidden="true" />
          )}
          {providerLabel}
        </span>
        <span style={{fontSize: '11px', color: 'var(--color-text-muted)'}}>
          Score: {scorePct}% · {latencyMs}ms
        </span>

        {(retrievalConfidence === 'insufficient' || retrievalConfidence === 'low') && (
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              padding: '3px 8px',
              borderRadius: 'var(--radius-full)',
              fontSize: '11px',
              fontWeight: 500,
              backgroundColor: retrievalConfidence === 'insufficient' ? 'var(--color-error-bg)' : 'var(--color-warning-bg)',
              border: `1px solid ${retrievalConfidence === 'insufficient' ? 'var(--color-error-border)' : 'var(--color-warning-border)'}`,
              color: retrievalConfidence === 'insufficient' ? 'var(--color-error)' : 'var(--color-warning)',
            }}
            title={retrievalConfidence === 'insufficient' ? 'No matching context was retrieved for this query.' : 'Retrieved context had low semantic confidence.'}
          >
            <AlertTriangle size={10} aria-hidden="true" />
            {retrievalConfidence === 'insufficient' ? 'No retrieval context' : 'Low retrieval confidence'}
          </span>
        )}
      </motion.div>
    </motion.div>
  );
}
