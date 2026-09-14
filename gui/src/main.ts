import "./style.css";
import { fetchFiles, type FileInfo } from "./api";

const app = document.querySelector<HTMLDivElement>("#app")!;

app.innerHTML = `
  <main>
    <h1>Audio Files</h1>
    <div id="status"></div>
    <table id="files-table" hidden>
      <thead>
        <tr>
          <th>Name</th>
          <th>Size</th>
          <th>Duration</th>
          <th>Sample Rate</th>
          <th>Channels</th>
          <th>Bit Depth</th>
          <th>Codec</th>
          <th>Sample Format</th>
          <th>Created At</th>
        </tr>
      </thead>
      <tbody id="files-body"></tbody>
    </table>
  </main>
`;

const statusEl = document.querySelector<HTMLDivElement>("#status")!;
const tableEl = document.querySelector<HTMLTableElement>("#files-table")!;
const bodyEl = document.querySelector<HTMLTableSectionElement>("#files-body")!;

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(1)} ${units[unit]}`;
}

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = (seconds % 60).toFixed(1);
  return `${mins}:${secs.padStart(4, "0")}`;
}

function renderRow(file: FileInfo): string {
  return `
    <tr>
      <td>${file.name}</td>
      <td>${formatBytes(file.size_bytes)}</td>
      <td>${formatDuration(file.duration_seconds)}</td>
      <td>${file.sample_rate} Hz</td>
      <td>${file.channels}</td>
      <td>${file.bit_depth}-bit</td>
      <td>${file.codec}</td>
      <td>${file.sample_format}</td>
      <td>${new Date(file.created_at).toLocaleString()}</td>
    </tr>
  `;
}

async function loadFiles() {
  statusEl.textContent = "Loading…";
  try {
    const { items, total } = await fetchFiles();
    if (items.length === 0) {
      statusEl.textContent = "No files uploaded yet.";
      tableEl.hidden = true;
      return;
    }
    bodyEl.innerHTML = items.map(renderRow).join("");
    statusEl.textContent = `${total} file${total === 1 ? "" : "s"}`;
    tableEl.hidden = false;
  } catch (err) {
    statusEl.textContent = `Failed to load files: ${(err as Error).message}`;
    tableEl.hidden = true;
  }
}

loadFiles();
