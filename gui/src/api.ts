// Mirrors server/src/server/schemas.py (FileInfo, FileListResponse).

export interface FileInfo {
  name: string;
  size_bytes: number;
  duration_seconds: number;
  sample_rate: number;
  channels: number;
  bit_depth: number;
  codec: string;
  sample_format: string;
  created_at: string;
}

export interface FileListResponse {
  items: FileInfo[];
  total: number;
  limit: number;
  offset: number;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export async function fetchFiles(): Promise<FileListResponse> {
  const res = await fetch(`${API_BASE_URL}/files?fields=full`);
  if (!res.ok) {
    throw new Error(`GET /files?fields=full failed: ${res.status} ${res.statusText}`);
  }
  return res.json();
}
