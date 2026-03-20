/**
 * API client — all calls to the FastAPI backend.
 * Base URL from NEXT_PUBLIC_API_URL env var (defaults to localhost:8000).
 */

import axios from 'axios';

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

const api = axios.create({ baseURL: BASE });

// ── Types matching backend schemas exactly ─────────────────────────────────

export interface Session {
  session_id: string;
  domain: 'finance' | 'law' | 'global';
  session_name?: string | null;
  created_at: string;
}

export interface IngestResult {
  file_id: string;
  filename: string;
  domain: 'finance' | 'law' | 'global';
  chunk_count: number;
  status: string;
  folder_id?: string | null;
}

export interface FolderItem {
  folder_id: string;
  name: string;
  parent_id: string | null;
  user_id: string | null;
  shared_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface LLMResponse {
  insights: string[];
  warnings: string[];
  recommendations: string[];
  data: Record<string, unknown>;
}

export interface QueryResult {
  session_id: string;
  query: string;
  domain: 'finance' | 'law' | 'global';
  llm_provider: string;
  response: LLMResponse;
  chart_data: ChartData | null;
  retrieval_score_avg: number;
  retrieval_confidence: 'insufficient' | 'low' | 'normal' | 'unknown';
  latency_ms: number;
}

export interface ChartData {
  computed_at: string;
  category_totals: Record<string, number>;
  monthly_trends: { period: string; total: number }[];
  top_categories: string[];
  summary_stats: {
    total: number;
    avg_monthly: number;
    highest_category: string | null;
    currency?: string | null;
    currency_mode?: 'single' | 'mixed' | 'unknown';
    currency_breakdown?: Record<string, number>;
    highest_single_transaction: number;
    lowest_single_transaction: number;
  };
  bar_chart: { labels: string[]; values: number[] };
  line_chart: { periods: string[]; totals: number[] };
  pie_chart: { labels: string[]; values: number[] };
}

export interface Message {
  message_id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
  llm_provider?: string | null;
  retrieval_score_avg?: number | null;
  latency_ms?: number | null;
}

export interface LLMSettings {
  gemini_enabled: boolean;
  groq_enabled: boolean;
  gemini_model: string;
  groq_model: string;
  gemini_temperature: number;
  groq_temperature: number;
  top_p: number;
  gemini_max_output_tokens: number;
  groq_max_tokens: number;
  llm_timeout_seconds: number;
}

export interface HistoryResult {
  session_id: string;
  messages: Message[];
  total: number;
}

// ── API Functions ──────────────────────────────────────────────────────────

export async function createSession(
  domain: 'finance' | 'law' | 'global',
  userId?: string,
): Promise<Session> {
  const payload: { domain: 'finance' | 'law' | 'global'; user_id?: string } = { domain };
  if (userId) {
    payload.user_id = userId;
  }
  const res = await api.post<Session>('/api/v1/sessions', payload);
  return res.data;
}

export async function getSessions(userId: string): Promise<Session[]> {
  const res = await api.get<{sessions: Session[]}>('/api/v1/sessions', {
    params: { user_id: userId }
  });
  return res.data.sessions;
}

export async function deleteSession(sessionId: string): Promise<void> {
  await api.delete(`/api/v1/sessions/${sessionId}`);
}

export async function renameSession(sessionId: string, sessionName: string): Promise<void> {
  await api.patch(`/api/v1/sessions/${sessionId}`, { session_name: sessionName });
}

export async function ingestFile(
  sessionId: string,
  domain: 'finance' | 'law' | 'global',
  file: File,
  columnMapping?: Record<string, string>,
  folderId?: string,
): Promise<IngestResult> {
  const form = new FormData();
  form.append('file', file);
  form.append('domain', domain);
  form.append('session_id', sessionId);
  if (columnMapping) {
    form.append('column_mapping', JSON.stringify(columnMapping));
  }
  if (folderId) {
    form.append('folder_id', folderId);
  }
  const res = await api.post<IngestResult>('/api/v1/ingest', form);
  return res.data;
}

export async function deleteFile(fileId: string): Promise<void> {
  await api.delete(`/api/v1/files/${fileId}`);
}

export async function submitQuery(
  sessionId: string,
  domain: 'finance' | 'law' | 'global',
  query: string,
  fileId?: string,
): Promise<QueryResult> {
  const res = await api.post<QueryResult>('/api/v1/query', {
    session_id: sessionId,
    domain,
    query,
    file_id: fileId ?? null,
  });
  return res.data;
}

export async function getHistory(
  sessionId: string,
  limit = 20,
  offset = 0,
): Promise<HistoryResult> {
  const res = await api.get<HistoryResult>(
    `/api/v1/sessions/${sessionId}/history`,
    { params: { limit, offset } },
  );
  return res.data;
}

export async function getSessionFiles(sessionId: string): Promise<IngestResult[]> {
  const res = await api.get<IngestResult[]>(`/api/v1/sessions/${sessionId}/files`);
  return res.data;
}

export async function getFileChartData(fileId: string, query?: string): Promise<ChartData> {
  const res = await api.get<ChartData>(`/api/v1/files/${fileId}/chart`, {
    params: query ? { query } : undefined,
  });
  return res.data;
}

export async function createFolder(
  name: string,
  userId: string,
  parentId?: string,
): Promise<FolderItem> {
  const res = await api.post<FolderItem>('/api/v1/folders', {
    name,
    user_id: userId,
    parent_id: parentId ?? null,
  });
  return res.data;
}

export async function getFolders(userId: string, parentId?: string): Promise<FolderItem[]> {
  const res = await api.get<FolderItem[]>('/api/v1/folders', {
    params: {
      user_id: userId,
      parent_id: parentId,
    },
  });
  return res.data;
}

export async function updateFolder(
  folderId: string,
  userId: string,
  updates: {name?: string; parent_id?: string | null},
): Promise<FolderItem> {
  const res = await api.patch<FolderItem>(`/api/v1/folders/${folderId}`, {
    user_id: userId,
    ...updates,
  });
  return res.data;
}

export async function deleteFolder(folderId: string, userId: string): Promise<void> {
  await api.delete(`/api/v1/folders/${folderId}`, {
    params: {user_id: userId},
  });
}

export async function shareFolder(folderId: string, userId: string): Promise<void> {
  await api.post(`/api/v1/folders/${folderId}/share`, {user_id: userId});
}

export async function makeFolderPrivate(folderId: string, userId: string): Promise<void> {
  await api.post(`/api/v1/folders/${folderId}/private`, {user_id: userId});
}

export async function toolTree(
  userId: string,
  rootFolderId?: string,
  maxDepth = 6,
  maxItems = 500,
): Promise<Record<string, unknown>> {
  const res = await api.get('/api/v1/tools/tree', {
    params: {
      user_id: userId,
      root_folder_id: rootFolderId,
      max_depth: maxDepth,
      max_items: maxItems,
    },
  });
  return res.data;
}

export async function toolLs(userId: string, folderId?: string): Promise<Record<string, unknown>> {
  const res = await api.get('/api/v1/tools/ls', {
    params: {
      user_id: userId,
      folder_id: folderId,
    },
  });
  return res.data;
}

export async function getLLMSettings(): Promise<LLMSettings> {
  const res = await api.get<LLMSettings>('/api/v1/settings/llm');
  return res.data;
}

export async function updateLLMSettings(payload: LLMSettings): Promise<LLMSettings> {
  const res = await api.put<LLMSettings>('/api/v1/settings/llm', payload);
  return res.data;
}
