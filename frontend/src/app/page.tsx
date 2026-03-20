'use client';

/**
 * Main chat page — wires all components together.
 * Manages: domain, sessions, active session, messages, files, loading, errors.
 */

import React, {useCallback, useEffect, useRef, useState} from 'react';
import {XCircle, AlertTriangle} from 'lucide-react';
import {motion, useAnimationControls} from 'framer-motion';

import Sidebar from '@/components/Sidebar';
import TopBar from '@/components/TopBar';
import InputBar from '@/components/InputBar';
import EmptyState from '@/components/EmptyState';
import ChartPanel from '@/components/ChartPanel';
import SettingsModal from '@/components/SettingsModal';
import {UserMessage, AssistantMessage, AssistantLoading} from '@/components/ChatMessage';

import {
  createSession,
  deleteSession,
  renameSession,
  submitQuery,
  getHistory,
  getSessions,
  getSessionFiles,
  getFileChartData,
  ingestFile,
  deleteFile,
} from '@/lib/api';
import type {Session, IngestResult, QueryResult, Message, ChartData} from '@/lib/api';
import { authClient } from '@/lib/auth-client';
import { useRouter } from 'next/navigation';

interface ChatTurn {
  userQuery: string;
  result?: QueryResult;
  loading: boolean;
}

interface HistoryFetchResult {
  messages: Message[];
  total: number;
}

interface BackendErrorPayload {
  error?: string;
  detail?: string;
  error_code?: string;
  details?: {
    found_columns?: string[];
  };
}

interface DeleteCandidate {
  type: 'session' | 'file';
  id: string;
  label: string;
}

function isFinanceSummaryQuery(query: string): boolean {
  return /\b(summary|overview|spending summary|expense summary|highlights|spending highlights|usage patterns|behavior insights|total spent)\b/i.test(query);
}

function wantsFinanceVisualization(query: string): boolean {
  return /graph|chart|trend|plot|visual|breakdown|pie|stock|price|performance|compare|volatility|analy[sz]e?|insight/i.test(query)
    || isFinanceSummaryQuery(query);
}

export default function ChatPage() {
  const [domain, setDomain] = useState<'finance' | 'law' | 'global'>('finance');
  const [sessions, setSessions] = useState<Session[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [files, setFiles] = useState<IngestResult[]>([]);
  const [filesLoading, setFilesLoading] = useState(false);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [activeChart, setActiveChart] = useState<{data: ChartData; idx: number} | null>(null);
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadLoading, setUploadLoading] = useState(false);
  
  // Mapping Modal State
  const [isMappingModalOpen, setIsMappingModalOpen] = useState(false);
  const [mappingFile, setMappingFile] = useState<File | null>(null);
  const [mappingFoundColumns, setMappingFoundColumns] = useState<string[]>([]);
  const [columnMapping, setColumnMapping] = useState<Record<string, string>>({});
  const [isMobile, setIsMobile] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [deleteCandidate, setDeleteCandidate] = useState<DeleteCandidate | null>(null);

  const bottomRef = useRef<HTMLDivElement>(null);
  const chatFadeControls = useAnimationControls();
  
  const { data: authSession, isPending: authPending } = authClient.useSession();
  const router = useRouter();

  const activeSession = sessions.find((s) => s.session_id === activeSessionId) ?? null;
  const hasFile = files.some((f) => f.status === 'indexed');
  const isLoading = turns.some((t) => t.loading);

  useEffect(() => {
    const media = window.matchMedia('(max-width: 1023px)');
    const sync = () => {
      setIsMobile(media.matches);
      setIsSidebarOpen(!media.matches);
    };
    sync();
    media.addEventListener('change', sync);
    return () => media.removeEventListener('change', sync);
  }, []);

  useEffect(() => {
    const run = async () => {
      await chatFadeControls.start({
        opacity: 0.65,
        transition: {duration: 0.14, ease: 'easeOut'},
      });
      await chatFadeControls.start({
        opacity: 1,
        transition: {duration: 0.22, ease: 'easeOut'},
      });
    };
    run();
  }, [isSidebarOpen, chatFadeControls]);

  /* Auth Enforcement */
  useEffect(() => {
    if (!authPending && !authSession) {
      router.push('/login');
    }
  }, [authPending, authSession, router]);

  /* Load user sessions on mount */
  useEffect(() => {
    if (authSession?.user?.id) {
      setSessionsLoading(true);
      getSessions(authSession.user.id)
        .then(setSessions)
        .catch(() => { /* non-fatal error */ })
        .finally(() => setSessionsLoading(false));
    }
  }, [authSession?.user?.id]);

  /* Auto-scroll to bottom */
  useEffect(() => {
    bottomRef.current?.scrollIntoView({behavior: 'smooth'});
  }, [turns]);

  /* Auto-dismiss error after 6s (ui.md Section 9.8) */
  useEffect(() => {
    if (!error) return;
    const t = setTimeout(() => setError(null), 6000);
    return () => clearTimeout(t);
  }, [error]);

  /* Load history when session changes */
  useEffect(() => {
    if (!activeSessionId) return;
    setIsHistoryLoading(true);
    setFilesLoading(true);
    setTurns([]);
    setFiles([]);
    setActiveChart(null);
    
    Promise.all([
      getHistory(activeSessionId)
        .catch((): HistoryFetchResult => ({ messages: [], total: 0 })), // safe fallback
      getSessionFiles(activeSessionId)
        .catch((): IngestResult[] => []) // safe fallback
    ]).then(async ([h, f]) => {
      setFiles(f); // Reload uploaded files

      let sessionChartFileId: string | null = null;
      if (domain === 'finance') {
        const indexedFile = f.find(file => file.status === 'indexed');
        if (indexedFile) sessionChartFileId = indexedFile.file_id;
      }

      // Reconstruct turns from history pairs
      const userMsgs = h.messages.filter((m) => m.role === 'user');
      const asstMsgs = h.messages.filter((m) => m.role === 'assistant');
      const reconstructed: ChatTurn[] = await Promise.all(userMsgs.map(async (um: Message, i: number) => {
        const asstMsg = asstMsgs[i] as Message | undefined;
        let result: QueryResult | undefined;
        if (asstMsg) {
          try {
            const parsed = JSON.parse(asstMsg.content);
            const wantsChart = wantsFinanceVisualization(um.content);

            // Fetch chart data with the original query for proper filtering
            let chartData = null;
            if (wantsChart && sessionChartFileId) {
              try {
                chartData = await getFileChartData(sessionChartFileId, um.content);
              } catch { /* ignore */ }
            }

            result = {
              session_id: activeSessionId,
              query: um.content,
              domain: domain,
              // Use real metadata stored in DB, fall back to defaults
              llm_provider: asstMsg.llm_provider ?? 'none',
              response: parsed,
              chart_data: chartData,
              retrieval_score_avg: asstMsg.retrieval_score_avg ?? 0,
              retrieval_confidence:
                Array.isArray(parsed?.warnings) && parsed.warnings.includes('Insufficient data to generate insights.')
                  ? 'insufficient'
                  : 'unknown',
              latency_ms: asstMsg.latency_ms ?? 0,
            };
          } catch {
            // content is plain text, not a structured piece of JSON — skip
          }
        }
        return {userQuery: um.content, result, loading: false};
      }));
      setTurns(reconstructed);
      setIsHistoryLoading(false);
      setFilesLoading(false);
    }).catch(() => {
      setTurns([]);
      setFiles([]);
      setIsHistoryLoading(false);
      setFilesLoading(false);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeSessionId]);

  const handleNewSession = useCallback(async () => {
    try {
      const s = await createSession(domain, authSession?.user?.id);
      setSessions((prev) => [s, ...prev]);
      setActiveSessionId(s.session_id);
      setTurns([]);
      setFiles([]);
      setActiveChart(null);
    } catch {
      setError('Failed to create session. Check that the backend is running.');
    }
  }, [domain, authSession?.user?.id]);

  const handleDeleteSession = useCallback((id: string) => {
    const session = sessions.find((s) => s.session_id === id);
    setDeleteCandidate({
      type: 'session',
      id,
      label: session ? `${session.domain} session (${new Date(session.created_at).toLocaleDateString('en-US')})` : 'this session',
    });
  }, [sessions]);

  const handleRenameSession = useCallback(async (id: string, newName: string) => {
    const trimmed = newName.trim();
    if (!trimmed) return;

    const previousName = sessions.find((s) => s.session_id === id)?.session_name ?? null;
    setSessions((prev) => prev.map((s) => (s.session_id === id ? { ...s, session_name: trimmed } : s)));

    try {
      await renameSession(id, trimmed);
    } catch (e: unknown) {
      setSessions((prev) => prev.map((s) => (s.session_id === id ? { ...s, session_name: previousName } : s)));
      const respData = (e as { response?: { data?: BackendErrorPayload } })?.response?.data;
      const msg = respData?.error || respData?.detail || 'Failed to rename session.';
      setError(msg);
    }
  }, [sessions]);

  const confirmDelete = useCallback(async () => {
    if (!deleteCandidate) return;

    try {
      if (deleteCandidate.type === 'session') {
        await deleteSession(deleteCandidate.id);
        setSessions((prev) => prev.filter((s) => s.session_id !== deleteCandidate.id));
        if (activeSessionId === deleteCandidate.id) {
          setActiveSessionId(null);
          setTurns([]);
          setFiles([]);
        }
      } else {
        await deleteFile(deleteCandidate.id);
        setFiles((prev) => prev.filter((f) => f.file_id !== deleteCandidate.id));
        setActiveChart(null);
      }
      setDeleteCandidate(null);
    } catch {
      setError(deleteCandidate.type === 'session' ? 'Failed to delete session.' : 'Failed to delete file.');
    }
  }, [activeSessionId, deleteCandidate]);

  const handleSessionSelect = useCallback((id: string) => {
    const selected = sessions.find((s) => s.session_id === id);
    if (selected) {
      setDomain(selected.domain);
    }
    setActiveSessionId(id);
  }, [sessions]);

  const handleDeleteFile = useCallback((id: string) => {
    const file = files.find((f) => f.file_id === id);
    setDeleteCandidate({
      type: 'file',
      id,
      label: file?.filename ?? 'this file',
    });
  }, [files]);

  const handleDomainChange = useCallback((d: 'finance' | 'law' | 'global') => {
    setDomain(d);
    setActiveSessionId(null);
    setTurns([]);
    setFiles([]);
  }, []);

  const handleFileSelect = useCallback(async (file: File, userMapping?: Record<string, string>) => {
    if (!activeSessionId) {
      setError('Create a session first before uploading a file.');
      return;
    }

    const optimisticId = `upload-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const optimisticFile: IngestResult = {
      file_id: optimisticId,
      filename: file.name,
      domain,
      chunk_count: 0,
      status: 'processing',
      folder_id: null,
    };

    setFiles((prev) => [
      ...prev.filter((f) => !(f.filename === file.name && (f.status === 'processing' || f.status === 'failed'))),
      optimisticFile,
    ]);

    setUploadLoading(true);
    try {
      const result = await ingestFile(activeSessionId, domain, file, userMapping);
      setFiles((prev) => {
        const replaced = prev.map((f) => (f.file_id === optimisticId ? result : f));
        const found = replaced.some((f) => f.file_id === result.file_id || f.file_id === optimisticId);
        return found ? replaced : [...replaced, result];
      });
    } catch (e: unknown) {
      const respData = (e as { response?: { data?: BackendErrorPayload } })?.response?.data;

      setFiles((prev) => {
        let updated = false;
        const next = prev.map((f) => {
          if (f.file_id === optimisticId) {
            updated = true;
            return { ...f, status: 'failed' };
          }
          return f;
        });
        if (updated) return next;

        return [
          ...next,
          {
            file_id: optimisticId,
            filename: file.name,
            domain,
            chunk_count: 0,
            status: 'failed',
            folder_id: null,
          },
        ];
      });

      if (respData?.error_code === 'MISSING_REQUIRED_COLUMNS' && respData?.details?.found_columns) {
        setMappingFoundColumns(respData.details.found_columns);
        setMappingFile(file);
        setIsMappingModalOpen(true);
        setError(null);
      } else {
        const msg = respData?.error || respData?.detail || 'File ingestion failed. Check if the file format matches the selected domain.';
        setError(msg);
      }
    } finally {
      // Don't hide loading spinner if we're just about to show the modal... actually wait, the modal needs input.
      // So yes, hide loading spinner.
      setUploadLoading(false);
    }
  }, [activeSessionId, domain]);

  const handleQuery = useCallback(async (query: string) => {
    if (!activeSessionId) return;
    const turnId = turns.length;
    setTurns((prev) => [...prev, {userQuery: query, loading: true}]);

    const indexedFiles = files.filter((f) => f.status === 'indexed');
    const fileId = indexedFiles.length > 0 ? indexedFiles[indexedFiles.length - 1].file_id : undefined;
    try {
      let result = await submitQuery(activeSessionId, domain, query, fileId);

      if (domain === 'finance' && fileId && wantsFinanceVisualization(query) && !result.chart_data) {
        try {
          const chartData = await getFileChartData(fileId, query);
          result = {...result, chart_data: chartData};
        } catch {
          // If chart computation fails, keep the original answer card unchanged.
        }
      }

      setTurns((prev) =>
        prev.map((t, i) =>
          i === turnId ? {userQuery: query, result, loading: false} : t,
        ),
      );
      if (result.chart_data) {
        setActiveChart({ data: result.chart_data, idx: turnId });
      }
    } catch (e: unknown) {
      const msg = (e as {response?: {data?: {detail?: string}}})?.response?.data?.detail
        ?? 'Query failed. Please try again.';
      setError(msg);
      setTurns((prev) => prev.filter((_, i) => i !== turnId));
    }
  }, [activeSessionId, domain, files, turns.length]);

  // No persistent dual-column. Charts are dynamically toggled inline inside AssistantMessages.

  return (
    <div style={{display: 'flex', height: '100vh', overflow: 'hidden', backgroundColor: 'var(--color-bg-page)'}}>
      {/* Sidebar */}
      {isMobile ? (
        <Sidebar
          domain={domain}
          sessions={sessions}
          sessionsLoading={sessionsLoading}
          activeSessionId={activeSessionId}
          files={files}
          filesLoading={filesLoading}
          isMobile={isMobile}
          isOpen={isSidebarOpen}
          onCloseMobile={() => setIsSidebarOpen(false)}
          onDomainChange={handleDomainChange}
          onSessionSelect={(id) => {
            handleSessionSelect(id);
            if (isMobile) setIsSidebarOpen(false);
          }}
          onNewSession={handleNewSession}
          onRenameSession={handleRenameSession}
          onDeleteSession={handleDeleteSession}
          onDeleteFile={handleDeleteFile}
          onOpenSettings={() => setIsSettingsOpen(true)}
        />
      ) : (
        <motion.div
          initial={false}
          animate={{
            width: isSidebarOpen ? 240 : 0,
            opacity: isSidebarOpen ? 1 : 0,
          }}
          transition={{duration: 0.22, ease: 'easeInOut'}}
          style={{overflow: 'hidden', flexShrink: 0}}
        >
          <Sidebar
            domain={domain}
            sessions={sessions}
            sessionsLoading={sessionsLoading}
            activeSessionId={activeSessionId}
            files={files}
            filesLoading={filesLoading}
            isMobile={isMobile}
            isOpen={true}
            onCloseMobile={() => setIsSidebarOpen(false)}
            onDomainChange={handleDomainChange}
            onSessionSelect={(id) => {
              handleSessionSelect(id);
              if (isMobile) setIsSidebarOpen(false);
            }}
            onNewSession={handleNewSession}
            onRenameSession={handleRenameSession}
            onDeleteSession={handleDeleteSession}
            onDeleteFile={handleDeleteFile}
            onOpenSettings={() => setIsSettingsOpen(true)}
          />
        </motion.div>
      )}

      {isMobile && isSidebarOpen && (
        <div
          onClick={() => setIsSidebarOpen(false)}
          aria-hidden="true"
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(2, 6, 23, 0.45)',
            zIndex: 20,
          }}
        />
      )}

      {/* Main content */}
      <motion.div
        layout
        animate={chatFadeControls}
        style={{flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden'}}
      >
        <TopBar
          domain={domain}
          title={activeSession ? undefined : 'New Session'}
          showSidebarToggle={true}
          isSidebarOpen={isSidebarOpen}
          onToggleSidebar={() => setIsSidebarOpen((prev) => !prev)}
        />

        {/* Error banner (ui.md Section 9.8) */}
        {error && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '10px 24px',
              backgroundColor: 'var(--color-error-bg)',
              border: '1px solid var(--color-error-border)',
              borderRadius: 'var(--radius-md)',
              margin: '8px 24px 0',
              fontSize: '13px',
              color: 'var(--color-error)',
            }}
          >
            <XCircle size={14} aria-hidden="true" />
            <span style={{flex: 1}}>{error}</span>
            <button
              onClick={() => setError(null)}
              aria-label="Dismiss error"
              style={{background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-error)', padding: '2px'}}
            >
              ×
            </button>
          </div>
        )}

        {/* Upload loading indicator */}
        {uploadLoading && (
          <div style={{padding: '8px 24px', fontSize: '13px', color: 'var(--color-text-muted)'}}>
            Uploading and indexing file…
          </div>
        )}

        {/* No session selected */}
        {!activeSessionId ? (
          <div style={{flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
            <div style={{textAlign: 'center'}}>
              <p style={{color: 'var(--color-text-muted)', fontSize: '14px', marginBottom: '16px'}}>
                Select or create a session to get started
              </p>
              <button
                onClick={handleNewSession}
                style={{
                  padding: '10px 20px',
                  borderRadius: 'var(--radius-md)',
                  border: 'none',
                  backgroundColor: 'var(--color-accent)',
                  color: '#FFFFFF',
                  fontSize: '14px',
                  cursor: 'pointer',
                }}
              >
                New Session
              </button>
            </div>
          </div>
        ) : (
          <>
            {/* Chat Area Container */}
            <div style={{flex: 1, display: 'flex', overflow: 'hidden'}}>
              <div
                style={{
                  flex: activeChart ? '0 0 60%' : '1',
                  overflowY: 'auto',
                  padding: '24px',
                  display: 'flex',
                  flexDirection: 'column',
                }}
              >
                <div style={{width: '100%', maxWidth: '920px', margin: '0 auto'}}>
                  {isHistoryLoading ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                         <div className="shimmer" style={{ width: '40%', height: '48px', borderRadius: '12px', opacity: 0.5 }} />
                      </div>
                      <AssistantLoading />
                      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                         <div className="shimmer" style={{ width: '60%', height: '48px', borderRadius: '12px', opacity: 0.5 }} />
                      </div>
                      <AssistantLoading />
                    </div>
                  ) : turns.length === 0 && !isLoading ? (
                    <EmptyState domain={domain} onFileSelect={handleFileSelect} />
                  ) : (
                    turns.map((turn, i) => (
                      <div key={i} style={{display: 'flex', flexDirection: 'column', width: '100%'}}>
                        <UserMessage content={turn.userQuery} />
                        {turn.loading ? (
                          <AssistantLoading />
                        ) : turn.result ? (
                          <AssistantMessage
                            result={turn.result}
                            turnIndex={i}
                            activeChartTurnIdx={activeChart?.idx ?? null}
                            onToggleChart={(data, idx) => {
                              setActiveChart(data && idx !== null ? {data, idx} : null);
                            }}
                          />
                        ) : null}
                      </div>
                    ))
                  )}
                </div>
                <div ref={bottomRef} style={{height: 1}} />
              </div>

              {/* Chart Side Panel */}
              {activeChart && (
                <div
                  style={{
                    flex: '1',
                    borderLeft: '1px solid var(--color-border-base)',
                    backgroundColor: 'var(--color-bg-muted)',
                    padding: '24px',
                    overflowY: 'auto',
                  }}
                >
                  <ChartPanel chartData={activeChart.data} />
                </div>
              )}
            </div>

            {/* Input bar */}
            <InputBar
              disabled={!hasFile && turns.length === 0}
              loading={isLoading}
              accept={domain === 'finance' ? '.csv' : domain === 'law' ? '.pdf,.txt' : '.csv,.pdf,.txt'}
              onSubmit={handleQuery}
              onFileSelect={handleFileSelect}
            />
          </>
        )}
      </motion.div>

      {/* Mapping Modal Animation Styles */}
      <style>{`
        @keyframes mappingOverlayFadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes mappingCardSlideIn {
          from { opacity: 0; transform: scale(0.92) translateY(12px); }
          to { opacity: 1; transform: scale(1) translateY(0); }
        }
        .mapping-overlay {
          position: fixed; top: 0; left: 0; right: 0; bottom: 0;
          background: rgba(0,0,0,0.5);
          backdrop-filter: blur(4px);
          z-index: 1000;
          display: flex; align-items: center; justify-content: center;
          animation: mappingOverlayFadeIn 0.25s ease-out;
        }
        .mapping-card {
          background: var(--color-bg-page);
          padding: 28px;
          border-radius: var(--radius-lg, 12px);
          width: 420px; max-width: 92%;
          border: 1px solid var(--color-border-base);
          box-shadow: 0 20px 60px rgba(0,0,0,0.3);
          animation: mappingCardSlideIn 0.3s ease-out;
        }
        .mapping-card h3 {
          margin: 0 0 6px; font-size: 18px; font-weight: 600; color: var(--color-text-primary);
        }
        .mapping-card p.mapping-desc {
          font-size: 13px; color: var(--color-text-muted); margin: 0 0 22px; line-height: 1.5;
        }
        .mapping-field { margin-bottom: 18px; }
        .mapping-field label {
          display: block; margin-bottom: 6px; font-size: 13px; font-weight: 600;
          color: var(--color-text-body); letter-spacing: 0.02em;
        }
        .mapping-field label .mapping-badge {
          display: inline-block; font-size: 11px; font-weight: 500;
          padding: 1px 6px; border-radius: 4px; margin-left: 6px; vertical-align: middle;
        }
        .mapping-badge.required { background: rgba(239,68,68,0.15); color: #EF4444; }
        .mapping-badge.optional { background: var(--color-accent-subtle); color: var(--color-accent); }
        .mapping-field select {
          width: 100%; padding: 9px 12px; border-radius: var(--radius-md, 6px);
          border: 1px solid var(--color-border-base);
          background: var(--color-bg-surface, var(--color-bg-page));
          color: var(--color-text-body); font-size: 14px;
          transition: border-color 0.2s ease, box-shadow 0.2s ease;
          outline: none; cursor: pointer;
        }
        .mapping-field select:focus {
          border-color: var(--color-accent);
          box-shadow: 0 0 0 3px var(--color-accent-subtle);
        }
        .mapping-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 24px; }
        .mapping-btn {
          padding: 9px 18px; border-radius: var(--radius-md, 6px);
          font-size: 14px; font-weight: 500; cursor: pointer;
          transition: all 0.2s ease;
        }
        .mapping-btn-cancel {
          border: 1px solid var(--color-border-base);
          background: transparent; color: var(--color-text-body);
        }
        .mapping-btn-cancel:hover { background: var(--color-accent-subtle); }
        .mapping-btn-save {
          border: 1px solid var(--color-accent);
          background: var(--color-accent); color: #fff;
        }
        .mapping-btn-save:hover:not(:disabled) {
          background: var(--color-accent-hover); border-color: var(--color-accent-hover);
          box-shadow: 0 2px 8px rgba(20,184,166,0.3);
        }
        .mapping-btn-save:disabled {
          opacity: 0.45; cursor: not-allowed;
        }
      `}</style>

      {/* Mapping Modal */}
      {isMappingModalOpen && mappingFile && (
        <div className="mapping-overlay">
          <div className="mapping-card">
            <h3>Map Your Columns</h3>
            <p className="mapping-desc">
              We couldn&apos;t auto-detect the required columns. Please tell us which columns from your file correspond to each field.
            </p>
            
            <div className="mapping-field">
              <label>Date <span className="mapping-badge optional">Optional</span></label>
              <select 
                value={Object.keys(columnMapping).find(k => columnMapping[k] === 'date') || ''}
                onChange={(e) => {
                  const newMapping = { ...columnMapping };
                  for (const k in newMapping) if (newMapping[k] === 'date') delete newMapping[k];
                  if (e.target.value) newMapping[e.target.value] = 'date';
                  setColumnMapping(newMapping);
                }}
              >
                <option value="">None</option>
                {mappingFoundColumns.map(col => <option key={col} value={col}>{col}</option>)}
              </select>
            </div>

            <div className="mapping-field">
              <label>Amount <span className="mapping-badge required">Required</span></label>
              <select
                value={Object.keys(columnMapping).find(k => columnMapping[k] === 'amount') || ''}
                onChange={(e) => {
                  const newMapping = { ...columnMapping };
                  for (const k in newMapping) if (newMapping[k] === 'amount') delete newMapping[k];
                  if (e.target.value) newMapping[e.target.value] = 'amount';
                  setColumnMapping(newMapping);
                }}
              >
                <option value="">Select a column…</option>
                {mappingFoundColumns.map(col => <option key={col} value={col}>{col}</option>)}
              </select>
            </div>

            <div className="mapping-field">
              <label>Category <span className="mapping-badge optional">Optional</span></label>
              <select
                value={Object.keys(columnMapping).find(k => columnMapping[k] === 'category') || ''}
                onChange={(e) => {
                  const newMapping = { ...columnMapping };
                  for (const k in newMapping) if (newMapping[k] === 'category') delete newMapping[k];
                  if (e.target.value) newMapping[e.target.value] = 'category';
                  setColumnMapping(newMapping);
                }}
              >
                <option value="">None</option>
                {mappingFoundColumns.map(col => <option key={col} value={col}>{col}</option>)}
              </select>
            </div>

            <div className="mapping-actions">
              <button 
                className="mapping-btn mapping-btn-cancel"
                onClick={() => { setIsMappingModalOpen(false); setMappingFile(null); setColumnMapping({}); }}
              >
                Cancel
              </button>
              <button 
                className="mapping-btn mapping-btn-save"
                disabled={!Object.values(columnMapping).includes('amount')}
                onClick={() => {
                  setIsMappingModalOpen(false);
                  const file = mappingFile;
                  setMappingFile(null);
                  handleFileSelect(file, columnMapping);
                  setColumnMapping({});
                }}
              >
                Save &amp; Retry
              </button>
            </div>
          </div>
        </div>
      )}

      {deleteCandidate && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(2, 6, 23, 0.45)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1100,
            padding: '16px',
          }}
        >
          <div
            style={{
              width: '100%',
              maxWidth: '460px',
              backgroundColor: 'var(--color-bg-surface)',
              borderRadius: 'var(--radius-lg)',
              border: '1px solid var(--color-border-base)',
              borderTop: '3px solid var(--color-error)',
              boxShadow: 'var(--shadow-lg)',
              padding: '18px',
            }}
          >
            <div style={{display: 'flex', gap: '10px', alignItems: 'center', marginBottom: '10px'}}>
              <AlertTriangle size={18} style={{color: 'var(--color-error)'}} aria-hidden="true" />
              <h3 style={{margin: 0, fontSize: '18px', color: 'var(--color-text-primary)'}}>Confirm delete</h3>
            </div>
            <p style={{margin: 0, fontSize: '14px', color: 'var(--color-text-body)', lineHeight: 1.5}}>
              You are about to permanently delete {deleteCandidate.label}. This action cannot be undone.
            </p>
            <div style={{display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '16px'}}>
              <button
                onClick={() => setDeleteCandidate(null)}
                style={{
                  minWidth: '96px',
                  height: '44px',
                  padding: '0 16px',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--color-border-base)',
                  backgroundColor: 'transparent',
                  color: 'var(--color-text-body)',
                  cursor: 'pointer',
                }}
              >
                Cancel
              </button>
              <button
                onClick={confirmDelete}
                style={{
                  minWidth: '116px',
                  height: '44px',
                  padding: '0 16px',
                  borderRadius: 'var(--radius-md)',
                  border: 'none',
                  backgroundColor: 'var(--color-error)',
                  color: '#FFFFFF',
                  cursor: 'pointer',
                }}
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      <SettingsModal isOpen={isSettingsOpen} onClose={() => setIsSettingsOpen(false)} />
    </div>
  );
}
