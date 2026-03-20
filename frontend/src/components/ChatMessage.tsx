'use client';

/**
 * ChatMessage — renders a single chat turn.
 * User bubble (right-aligned) or assistant cards (left-aligned).
 * Animations: ui.md Section 16.6 — slide-in 200ms ease-out.
 */

import React from 'react';
import {motion} from 'framer-motion';
import {User, Bot, BarChart2, ChevronRight} from 'lucide-react';
import InsightCards from '@/components/InsightCards';
import FinanceSummaryCard from '@/components/FinanceSummaryCard';
import type {QueryResult, ChartData} from '@/lib/api';

interface UserMessageProps {
  content: string;
}

interface AssistantMessageProps {
  result: QueryResult;
  turnIndex: number;
  activeChartTurnIdx: number | null;
  onToggleChart?: (data: ChartData | null, idx: number | null) => void;
}

/* Slide-in from right for user, from left for assistant (ui.md 16.6) */
const slideFromRight = {
  initial: {opacity: 0, x: 20},
  animate: {opacity: 1, x: 0, transition: {duration: 0.2, ease: 'easeOut' as const}},
};

const slideFromLeft = {
  initial: {opacity: 0, x: -12},
  animate: {opacity: 1, x: 0, transition: {duration: 0.2, ease: 'easeOut' as const}},
};

function isFinanceSummaryQuery(query: string, domain: 'finance' | 'law' | 'global'): boolean {
  if (domain !== 'finance') return false;
  return /\b(summary|overview|spending summary|expense summary|highlights|spending highlights|usage patterns|behavior insights|total spent)\b/i.test(query);
}

export function UserMessage({content}: UserMessageProps) {
  return (
    <motion.div
      {...slideFromRight}
      style={{display: 'flex', justifyContent: 'flex-end', marginBottom: '14px', width: '100%'}}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'flex-end',
          gap: '8px',
          width: '100%',
          maxWidth: 'min(92%, 860px)',
          marginLeft: 'auto',
        }}
      >
        <div
          style={{
            maxWidth: 'min(74%, 560px)',
            backgroundColor: 'var(--color-accent-active)',
            border: '1px solid var(--color-accent-active)',
            borderRadius: '18px',
            padding: '11px 14px',
            fontSize: '14px',
            color: 'var(--color-text-inverse)',
            lineHeight: 1.6,
            boxShadow: 'var(--shadow-sm)',
          }}
        >
          {content}
        </div>
        <div
          style={{
            width: '30px',
            height: '30px',
            borderRadius: '999px',
            border: '1px solid var(--color-border-base)',
            backgroundColor: 'var(--color-bg-surface)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
            marginTop: '2px',
          }}
        >
          <User size={14} aria-hidden="true" style={{color: 'var(--color-text-secondary)'}} />
        </div>
      </div>
    </motion.div>
  );
}

export function AssistantMessage({result, turnIndex, activeChartTurnIdx, onToggleChart}: AssistantMessageProps) {
  const isChartActive = activeChartTurnIdx === turnIndex;
  const showFinanceSummary = isFinanceSummaryQuery(result.query, result.domain) && !!result.chart_data;

  const handleToggle = () => {
    if (onToggleChart) {
      onToggleChart(
        isChartActive ? null : result.chart_data!,
        isChartActive ? null : turnIndex
      );
    }
  };

  return (
    <motion.div
      {...slideFromLeft}
      style={{display: 'flex', justifyContent: 'flex-start', marginBottom: '18px', width: '100%'}}
    >
      <div style={{display: 'flex', alignItems: 'flex-start', gap: '8px', width: '100%'}}>
        <div
          style={{
            width: '30px',
            height: '30px',
            borderRadius: '999px',
            border: '1px solid var(--color-border-base)',
            backgroundColor: 'var(--color-bg-surface)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
            marginTop: '2px',
          }}
        >
          <Bot size={14} aria-hidden="true" style={{color: 'var(--color-text-secondary)'}} />
        </div>
        <div
          style={{
            width: '100%',
            maxWidth: 'min(92%, 860px)',
            backgroundColor: 'var(--color-bg-surface)',
            border: '1px solid var(--color-border-base)',
            borderRadius: '16px',
            padding: '14px',
            boxShadow: 'var(--shadow-sm)',
          }}
        >
        {showFinanceSummary && result.chart_data && (
          <FinanceSummaryCard chartData={result.chart_data} response={result.response} />
        )}

        <InsightCards
          response={result.response}
          llmProvider={result.llm_provider}
          retrievalScoreAvg={result.retrieval_score_avg}
          retrievalConfidence={result.retrieval_confidence}
          latencyMs={result.latency_ms}
        />

        {result.chart_data && (
          <div style={{ marginTop: '14px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <button
              onClick={handleToggle}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                backgroundColor: isChartActive
                  ? 'var(--color-accent)'
                  : 'var(--color-bg-surface)',
                border: isChartActive
                  ? '1px solid var(--color-accent)'
                  : '1px solid var(--color-border-base)',
                color: isChartActive
                  ? '#ffffff'
                  : 'var(--color-text-primary)',
                padding: '8px 16px',
                borderRadius: 'var(--radius-md)',
                fontSize: '13px',
                fontWeight: 500,
                cursor: 'pointer',
                width: 'fit-content',
                transition: 'all 150ms ease',
                boxShadow: 'var(--shadow-sm)'
              }}
            >
              <BarChart2 size={16} aria-hidden="true" style={{ color: isChartActive ? '#ffffff' : 'var(--color-accent)' }} />
              <span>{isChartActive ? 'Hide Financial Charts' : 'View Financial Charts'}</span>
              <ChevronRight size={16} aria-hidden="true" style={{
                color: isChartActive ? '#ffffff' : 'var(--color-text-muted)',
                transform: isChartActive ? 'scaleX(-1)' : 'none',
                transition: 'transform 150ms ease'
              }} />
            </button>
          </div>
        )}
        </div>
      </div>
    </motion.div>
  );
}

/** Loading shimmer placeholder (ui.md Section 9.7) */
export function AssistantLoading() {
  return (
    <div style={{display: 'flex', justifyContent: 'flex-start', marginBottom: '16px'}}>
      <div style={{display: 'flex', alignItems: 'flex-start', gap: '8px', width: '100%'}}>
        <div
          style={{
            width: '30px',
            height: '30px',
            borderRadius: '999px',
            border: '1px solid var(--color-border-base)',
            backgroundColor: 'var(--color-bg-surface)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
            marginTop: '2px',
          }}
        >
          <Bot size={14} aria-hidden="true" style={{color: 'var(--color-text-secondary)'}} />
        </div>
        <div style={{display: 'flex', flexDirection: 'column', gap: '8px', width: '100%', maxWidth: 'min(92%, 860px)'}}>
          {[80, 60, 70].map((w, i) => (
            <div
              key={i}
              className="shimmer"
              style={{
                height: '16px',
                borderRadius: 'var(--radius-sm)',
                width: `${w}%`,
              }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
