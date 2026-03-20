'use client';

/**
 * ChartPanel — renders Finance domain chart data returned by the backend.
 * Uses Recharts. All colors from design system (ui.md Section 11).
 * No library defaults. No rainbow palettes.
 */

import React from 'react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  Area, AreaChart,
  PieChart, Pie, Cell, Legend,
} from 'recharts';
import type {ChartData} from '@/lib/api';

interface ChartPanelProps {
  chartData: ChartData;
}

/* Finance chart palette — ui.md Section 11.2 */
const PIE_COLORS = [
  '#14B8A6',
  '#0D9488',
  '#5EEAD4',
  '#64748B',
  '#94A3B8',
  '#CBD5E1',
];

const TOOLTIP_STYLE: React.CSSProperties = {
  backgroundColor: 'var(--color-bg-surface)',
  border: '1px solid var(--color-border-base)',
  borderRadius: '8px',
  fontSize: '12px',
  color: 'var(--color-text-body)',
  boxShadow: '0 4px 8px rgba(0,0,0,0.1)',
};

function SectionTitle({children}: {children: React.ReactNode}) {
  return (
    <h3
      style={{
        fontFamily: 'DM Sans, sans-serif',
        fontSize: '14px',
        fontWeight: 600,
        color: 'var(--color-text-primary)',
        marginBottom: '12px',
        marginTop: 0,
      }}
    >
      {children}
    </h3>
  );
}

function createMoneyFormatter(stats: ChartData['summary_stats']): (value: number) => string {
  if (stats.currency_mode === 'single' && stats.currency) {
    try {
      const nf = new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: stats.currency,
        maximumFractionDigits: 2,
      });
      return (value: number) => nf.format(value);
    } catch {
      // Invalid currency code; fallback to decimal formatting.
    }
  }

  const decimal = new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return (value: number) => decimal.format(value);
}

export default function ChartPanel({chartData}: ChartPanelProps) {
  const money = createMoneyFormatter(chartData.summary_stats);
  const hasMonthlyData = (chartData.line_chart.periods?.length ?? 0) > 0;
  const barData = chartData.bar_chart.labels.map((label, i) => ({
    name: label,
    value: chartData.bar_chart.values[i] ?? 0,
  }));

  const lineData = chartData.line_chart.periods.map((period, i) => ({
    period,
    total: chartData.line_chart.totals[i] ?? 0,
  }));

  const pieData = chartData.pie_chart.labels
    .map((label, i) => ({
      name: label,
      value: chartData.pie_chart.values[i] ?? 0,
    }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 6); // max 6 slices (ui.md Section 11.2)

  return (
    <div style={{display: 'flex', flexDirection: 'column', gap: '20px'}}>
      {/* Bar Chart — Category Totals */}
      <div
        style={{
          backgroundColor: 'var(--color-bg-surface)',
          border: '1px solid var(--color-border-base)',
          borderRadius: 'var(--radius-md)',
          boxShadow: 'var(--shadow-sm)',
          padding: '16px',
        }}
      >
        <SectionTitle>Category Totals</SectionTitle>
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={barData} margin={{top: 4, right: 4, left: -16, bottom: 4}}>
            <XAxis
              dataKey="name"
              tick={{fontSize: 11, fill: '#64748B'}}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{fontSize: 11, fill: '#64748B'}}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v: number) => (v >= 1000 ? `${(v / 1000).toFixed(1)}k` : `${v}`)}
            />
            <Tooltip
              contentStyle={TOOLTIP_STYLE}
              formatter={(v) => [money(Number(v)), 'Total']}
            />
            <Bar dataKey="value" fill="#14B8A6" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Area/Line Chart — Monthly Trends */}
      {lineData.length > 0 && (
        <div
          style={{
            backgroundColor: 'var(--color-bg-surface)',
            border: '1px solid var(--color-border-base)',
            borderRadius: 'var(--radius-md)',
            boxShadow: 'var(--shadow-sm)',
            padding: '16px',
          }}
        >
          <SectionTitle>Monthly Spending Trend</SectionTitle>
          <ResponsiveContainer width="100%" height={160}>
            <AreaChart data={lineData} margin={{top: 4, right: 4, left: -16, bottom: 4}}>
              <defs>
                <linearGradient id="tealGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#14B8A6" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#14B8A6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis
                dataKey="period"
                tick={{fontSize: 11, fill: '#64748B'}}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{fontSize: 11, fill: '#64748B'}}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v: number) => (v >= 1000 ? `${(v / 1000).toFixed(1)}k` : `${v}`)}
              />
              <Tooltip
                contentStyle={TOOLTIP_STYLE}
                formatter={(v) => [money(Number(v)), 'Total']}
              />
              <Area
                type="monotone"
                dataKey="total"
                stroke="#14B8A6"
                strokeWidth={2}
                fill="url(#tealGrad)"
                dot={{fill: '#14B8A6', r: 3, strokeWidth: 2, stroke: '#fff'}}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Pie Chart — Distribution */}
      {pieData.length > 0 && (
        <div
          style={{
            backgroundColor: 'var(--color-bg-surface)',
            border: '1px solid var(--color-border-base)',
            borderRadius: 'var(--radius-md)',
            boxShadow: 'var(--shadow-sm)',
            padding: '16px',
          }}
        >
          <SectionTitle>Category Distribution</SectionTitle>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie
                data={pieData}
                cx="50%"
                cy="50%"
                outerRadius={70}
                dataKey="value"
                stroke="var(--color-bg-surface)"
              >
                {pieData.map((_, i) => (
                  <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                ))}
              </Pie>
              <Legend
                iconSize={10}
                wrapperStyle={{fontSize: '11px', color: 'var(--color-text-secondary)'}}
              />
              <Tooltip
                contentStyle={TOOLTIP_STYLE}
                formatter={(v, _name, item) => [money(Number(v)), item?.payload?.name ?? 'Category']}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Summary Stats */}
      <div
        style={{
          backgroundColor: 'var(--color-bg-surface)',
          border: '1px solid var(--color-border-base)',
          borderRadius: 'var(--radius-md)',
          boxShadow: 'var(--shadow-sm)',
          padding: '16px',
        }}
      >
        <SectionTitle>Summary</SectionTitle>
        <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px'}}>
          {[
            ['Total', money(chartData.summary_stats.total)],
            ['Avg Monthly', hasMonthlyData ? money(chartData.summary_stats.avg_monthly) : '—'],
            ['Top Category', chartData.summary_stats.highest_category ?? '—'],
            ['Max Transaction', money(chartData.summary_stats.highest_single_transaction)],
          ].map(([label, value]) => (
            <div key={label}>
              <div style={{fontSize: '11px', color: 'var(--color-text-muted)', marginBottom: '2px'}}>{label}</div>
              <div style={{fontSize: '14px', fontWeight: 600, color: 'var(--color-text-primary)', fontFamily: 'JetBrains Mono, monospace'}}>
                {value}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
