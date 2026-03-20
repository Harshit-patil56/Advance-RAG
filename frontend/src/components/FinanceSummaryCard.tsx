'use client';

import React from 'react';
import {
  AlertTriangle,
  CreditCard,
  Coins,
  CircleDollarSign,
  Lightbulb,
  ShoppingBag,
  Trophy,
} from 'lucide-react';

import type {ChartData, LLMResponse} from '@/lib/api';

interface FinanceSummaryCardProps {
  chartData: ChartData;
  response: LLMResponse;
}

const numberFormatter = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function getNumericFromData(data: Record<string, unknown>, keys: string[]): number | null {
  for (const key of keys) {
    const raw = data[key];
    if (typeof raw === 'number' && Number.isFinite(raw)) return raw;
    if (typeof raw === 'string') {
      const parsed = Number(raw.replace(/,/g, ''));
      if (Number.isFinite(parsed)) return parsed;
    }
  }
  return null;
}

function extractTransactionCount(response: LLMResponse): number | null {
  const fromData = getNumericFromData(response.data ?? {}, [
    'transaction_count',
    'transactions',
    'total_transactions',
    'num_transactions',
    'count',
  ]);
  if (fromData !== null) return Math.round(fromData);

  const lines = [
    ...(response.insights ?? []),
    ...(response.warnings ?? []),
    ...(response.recommendations ?? []),
  ];
  for (const line of lines) {
    const match = line.match(/(\d+)\s+transactions?/i);
    if (match) return Number(match[1]);
  }
  return null;
}

function formatMoney(amount: number, currency: string | null | undefined, mode: string | null | undefined): string {
  if (mode === 'single' && currency) {
    try {
      return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency,
        maximumFractionDigits: 2,
      }).format(amount);
    } catch {
      // Invalid/unrecognized code; fall through to plain number format.
    }
  }
  return numberFormatter.format(amount);
}

export default function FinanceSummaryCard({chartData, response}: FinanceSummaryCardProps) {
  const stats = chartData.summary_stats;
  const transactionCount = extractTransactionCount(response);
  const currencyMode = stats.currency_mode ?? 'unknown';
  const currencyCode = stats.currency ?? null;

  const topCategoryRows = Object.entries(chartData.category_totals ?? {})
    .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
    .slice(0, 3);

  const behaviorRows = (chartData.top_categories ?? []).slice(0, 2);
  const hasMonthlyData = (chartData.monthly_trends?.length ?? 0) > 0;

  return (
    <div
      style={{
        backgroundColor: 'var(--color-bg-surface)',
        border: '1px solid var(--color-border-base)',
        borderRadius: 'var(--radius-lg)',
        boxShadow: 'var(--shadow-sm)',
        padding: '16px',
        marginBottom: '12px',
      }}
    >
      <h3
        style={{
          margin: 0,
          marginBottom: '12px',
          fontFamily: 'DM Sans, sans-serif',
          fontSize: '26px',
          lineHeight: 1.2,
          color: 'var(--color-text-primary)',
          fontWeight: 600,
        }}
      >
        Here&apos;s your spending summary:
      </h3>

      <div
        style={{
          border: '1px solid var(--color-border-base)',
          borderRadius: 'var(--radius-lg)',
          padding: '16px',
          backgroundColor: 'var(--color-bg-page)',
        }}
      >
        <div style={{display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px'}}>
          <Lightbulb size={18} aria-hidden="true" style={{color: 'var(--color-accent)'}} />
          <span style={{fontSize: '30px', fontWeight: 700, color: 'var(--color-text-primary)'}}>Overview</span>
        </div>

        {currencyMode === 'mixed' && (
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              backgroundColor: 'var(--color-warning-bg)',
              border: '1px solid var(--color-warning-border)',
              color: 'var(--color-warning)',
              borderRadius: 'var(--radius-full)',
              padding: '4px 10px',
              marginBottom: '12px',
              fontSize: '12px',
              fontWeight: 600,
            }}
          >
            <AlertTriangle size={12} aria-hidden="true" />
            Mixed currencies detected in this file
          </div>
        )}

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: transactionCount !== null ? 'repeat(2, minmax(0, 1fr))' : '1fr',
            gap: '12px',
            marginBottom: '12px',
          }}
        >
          <div
            style={{
              border: '1px solid var(--color-border-base)',
              borderRadius: 'var(--radius-md)',
              padding: '14px',
              backgroundColor: 'var(--color-bg-surface)',
              display: 'flex',
              gap: '10px',
              alignItems: 'center',
            }}
          >
            <div
              style={{
                width: '36px',
                height: '36px',
                borderRadius: 'var(--radius-sm)',
                backgroundColor: 'var(--color-accent-subtle)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <CircleDollarSign size={18} aria-hidden="true" style={{color: 'var(--color-accent)'}} />
            </div>
            <div>
              <div style={{fontSize: '30px', lineHeight: 1.1, fontWeight: 700, color: 'var(--color-text-primary)'}}>
                {formatMoney(stats.total, currencyCode, currencyMode)}
              </div>
              <div style={{fontSize: '16px', color: 'var(--color-text-secondary)'}}>
                {stats.total >= 0 ? 'Net Total' : 'Net Outflow'}
              </div>
            </div>
          </div>

          {transactionCount !== null && (
            <div
              style={{
                border: '1px solid var(--color-border-base)',
                borderRadius: 'var(--radius-md)',
                padding: '14px',
                backgroundColor: 'var(--color-bg-surface)',
                display: 'flex',
                gap: '10px',
                alignItems: 'center',
              }}
            >
              <div
                style={{
                  width: '36px',
                  height: '36px',
                  borderRadius: 'var(--radius-sm)',
                  backgroundColor: 'var(--color-accent-subtle)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <CreditCard size={18} aria-hidden="true" style={{color: 'var(--color-accent)'}} />
              </div>
              <div>
                <div style={{fontSize: '30px', lineHeight: 1.1, fontWeight: 700, color: 'var(--color-text-primary)'}}>
                  {transactionCount}
                </div>
                <div style={{fontSize: '16px', color: 'var(--color-text-secondary)'}}>Transactions</div>
              </div>
            </div>
          )}
        </div>

        <div
          style={{
            border: '1px solid var(--color-border-base)',
            borderRadius: 'var(--radius-md)',
            padding: '14px',
            backgroundColor: 'var(--color-bg-surface)',
            marginBottom: '12px',
          }}
        >
          <div style={{display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px'}}>
            <Coins size={18} aria-hidden="true" style={{color: 'var(--color-warning)'}} />
            <span style={{fontSize: '18px', fontWeight: 600, color: 'var(--color-text-primary)'}}>
              Spending Highlights
            </span>
          </div>
          <div style={{display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--color-text-body)'}}>
            <Trophy size={18} aria-hidden="true" style={{color: 'var(--color-warning)'}} />
            <span style={{fontSize: '30px', lineHeight: 1.1, fontWeight: 700, color: 'var(--color-text-primary)'}}>
              {formatMoney(stats.highest_single_transaction, currencyCode, currencyMode)}
            </span>
            <span style={{fontSize: '22px', color: 'var(--color-text-body)'}}>Highest Transaction</span>
          </div>
          <div style={{marginTop: '8px', fontSize: '14px', color: 'var(--color-text-secondary)'}}>
            Avg Monthly: {hasMonthlyData ? formatMoney(stats.avg_monthly, currencyCode, currencyMode) : '—'}
            {stats.highest_category ? ` · Top Category: ${stats.highest_category}` : ''}
          </div>
        </div>

        {(topCategoryRows.length > 0 || behaviorRows.length > 0) && (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
              gap: '12px',
              marginBottom: '4px',
            }}
          >
            {topCategoryRows.length > 0 && (
              <div>
                <div style={{display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px'}}>
                  <CreditCard size={18} aria-hidden="true" style={{color: 'var(--color-accent)'}} />
                  <span style={{fontSize: '18px', fontWeight: 600, color: 'var(--color-text-primary)'}}>
                    Usage Patterns
                  </span>
                </div>
                <div
                  style={{
                    border: '1px solid var(--color-border-base)',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: 'var(--color-bg-surface)',
                    overflow: 'hidden',
                  }}
                >
                  {topCategoryRows.map(([category, amount], idx) => (
                    <div
                      key={category}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '10px 12px',
                        borderBottom: idx < topCategoryRows.length - 1 ? '1px solid var(--color-border-base)' : 'none',
                        gap: '10px',
                      }}
                    >
                      <span style={{fontSize: '16px', color: 'var(--color-text-primary)', fontWeight: 500}}>{category}</span>
                      <span style={{fontSize: '15px', color: 'var(--color-text-secondary)'}}>{formatMoney(amount, currencyCode, currencyMode)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {behaviorRows.length > 0 && (
              <div>
                <div style={{display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px'}}>
                  <ShoppingBag size={18} aria-hidden="true" style={{color: 'var(--color-accent)'}} />
                  <span style={{fontSize: '18px', fontWeight: 600, color: 'var(--color-text-primary)'}}>
                    Behavior Insights
                  </span>
                </div>
                <div
                  style={{
                    border: '1px solid var(--color-border-base)',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: 'var(--color-bg-surface)',
                    overflow: 'hidden',
                  }}
                >
                  {behaviorRows.map((category, idx) => (
                    <div
                      key={`${category}-${idx}`}
                      style={{
                        padding: '10px 12px',
                        borderBottom: idx < behaviorRows.length - 1 ? '1px solid var(--color-border-base)' : 'none',
                        fontSize: '16px',
                        color: 'var(--color-text-primary)',
                        fontWeight: 500,
                      }}
                    >
                      {category}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}