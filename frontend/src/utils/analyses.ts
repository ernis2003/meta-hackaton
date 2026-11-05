import { useEffect, useState } from 'react';
import { BACKEND_URL, BACKEND_PORT } from '../../constants';
import { clearAuth } from './auth';
export type Analysis = {
  id: string;
  filename: string;
  status: string;
  uploaded_at: string;
  duration_seconds: number | null;
  error: string | null;
  summary: Record<string, unknown>;
  capabilities: Record<string, { status: string; reason: string; supported?: boolean }>;
};
export type Result = { id: string; [key: string]: unknown };
export type Page<T> = { items: T[]; total: number; limit: number; offset: number };
export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const token = sessionStorage.getItem('access_token');
  const response = await fetch(`${BACKEND_URL}:${BACKEND_PORT}/api/analyses${path}`, {
    ...options,
    headers: { Authorization: `Bearer ${token}`, ...options?.headers },
  });
  if (response.status === 401 && sessionStorage.getItem('access_token') === token) {
    clearAuth();
    window.location.replace('/?session=expired');
    throw new Error('Your session has expired. Please sign in again.');
  }
  const result = await response.json();
  if (!response.ok)
    throw new Error(
      typeof result.detail === 'string'
        ? result.detail
        : result.detail?.message || 'Request failed',
    );
  return result;
}
export function selectAnalysis(id: string) {
  sessionStorage.setItem('analysis_id', id);
  window.dispatchEvent(new Event('analysis-selected'));
}
export function useAnalysis() {
  const [id, setId] = useState(sessionStorage.getItem('analysis_id') || '');
  useEffect(() => {
    const update = () => setId(sessionStorage.getItem('analysis_id') || '');
    window.addEventListener('analysis-selected', update);
    return () => window.removeEventListener('analysis-selected', update);
  }, []);
  return id;
}
