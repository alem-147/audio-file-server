// Types generated from the server's OpenAPI spec: `npm run gen:api`
// (see src/api-schema.ts). Do not hand-write these.
import type { components } from "./api-schema";

export type FileInfo = components["schemas"]["FileInfo"];
export type FileListResponse = components["schemas"]["FileListResponse"];

// The generic FileListResponse.items is FileListItem[] | FileInfo[], since
// the server allows either shape depending on `?fields=`. This call always
// passes `fields=full`, so the server always returns FileInfo[] here.
type FullFileListResponse = Omit<FileListResponse, "items"> & { items: FileInfo[] };

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export async function fetchFiles(): Promise<FullFileListResponse> {
  const res = await fetch(`${API_BASE_URL}/files?fields=full`);
  if (!res.ok) {
    throw new Error(`GET /files?fields=full failed: ${res.status} ${res.statusText}`);
  }
  return res.json();
}
