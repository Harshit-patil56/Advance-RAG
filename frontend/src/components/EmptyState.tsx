'use client';

/**
 * EmptyState — shown when no files are uploaded (ui.md Section 9.6).
 * Finance shows BarChart2 + Upload CSV CTA.
 * Law shows Scale + Upload PDF/TXT CTA.
 * Animation: scale+fade entrance (ui.md 16.6).
 */

import React, {useRef} from 'react';
import {motion} from 'framer-motion';
import {BarChart2, Scale, Upload, Globe2} from 'lucide-react';

interface EmptyStateProps {
  domain: 'finance' | 'law' | 'global';
  onFileSelect: (file: File) => void;
}

export default function EmptyState({domain, onFileSelect}: EmptyStateProps) {
  const fileRef = useRef<HTMLInputElement>(null);

  const config = domain === 'finance'
    ? {
        icon: <BarChart2 size={48} aria-hidden="true" style={{color: '#CBD5E1'}} />,
        heading: 'Upload a Financial Document',
        subtext: 'Upload a CSV file to begin analyzing your financial data',
        btnLabel: 'Upload CSV',
        accept: '.csv',
        hint: 'Supported format: .csv',
      }
    : domain === 'law'
    ? {
        icon: <Scale size={48} aria-hidden="true" style={{color: '#CBD5E1'}} />,
        heading: 'Upload a Legal Document',
        subtext: 'Upload a PDF or TXT file to begin analyzing clauses and risks',
        btnLabel: 'Upload Document',
        accept: '.pdf,.txt',
        hint: 'Supported formats: .pdf, .txt',
      }
    : {
        icon: <Globe2 size={48} aria-hidden="true" style={{color: '#CBD5E1'}} />,
        heading: 'Upload Any Document',
        subtext: 'Upload CSV, PDF, or TXT files to run global analysis across mixed data',
        btnLabel: 'Upload File',
        accept: '.csv,.pdf,.txt',
        hint: 'Supported formats: .csv, .pdf, .txt',
      };

  return (
    <motion.div
      initial={{opacity: 0, scale: 0.97}}
      animate={{opacity: 1, scale: 1, transition: {duration: 0.3, ease: 'easeOut' as const}}}
      style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '16px',
        padding: '48px 24px',
      }}
    >
      <input
        ref={fileRef}
        type="file"
        accept={config.accept}
        style={{display: 'none'}}
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) {
            onFileSelect(f);
            e.target.value = '';
          }
        }}
      />

      {config.icon}

      <h2
        style={{
          fontFamily: 'DM Sans, sans-serif',
          fontSize: '18px',
          fontWeight: 500,
          color: '#475569',
          margin: 0,
          textAlign: 'center',
        }}
      >
        {config.heading}
      </h2>

      <p
        style={{
          fontSize: '13px',
          color: '#94A3B8',
          margin: 0,
          textAlign: 'center',
          maxWidth: '320px',
        }}
      >
        {config.subtext}
      </p>

      <motion.button
        onClick={() => fileRef.current?.click()}
        whileHover={{scale: 1.02}}
        whileTap={{scale: 0.98}}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '8px',
          padding: '12px 24px',
          borderRadius: 'var(--radius-md)',
          border: 'none',
          backgroundColor: 'var(--color-accent)',
          color: '#FFFFFF',
          fontSize: '14px',
          fontWeight: 500,
          cursor: 'pointer',
          minHeight: '44px',
        }}
      >
        <Upload size={16} aria-hidden="true" />
        {config.btnLabel}
      </motion.button>

      <span style={{fontSize: '11px', color: '#94A3B8'}}>{config.hint}</span>
    </motion.div>
  );
}
