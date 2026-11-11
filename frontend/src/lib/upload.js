// File uploads. With object storage (Cloudflare R2 / S3) the browser sends the file
// straight to storage using a signed URL, so no proxy size limit applies and LoNo never
// handles the bytes; otherwise it posts to LoNo, which streams the file to disk.
import { api } from "@/lib/api";

let modePromise = null;
const mode = () => (modePromise ||= api.get("/storage/mode").then((r) => r.data).catch(() => ({ direct: false })));

function putWithProgress(url, file, headers, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", url);
    Object.entries(headers || {}).forEach(([k, v]) => xhr.setRequestHeader(k, v));
    xhr.upload.onprogress = (e) => { if (e.lengthComputable) onProgress?.(Math.round((e.loaded / e.total) * 100)); };
    xhr.onload = () => (xhr.status >= 200 && xhr.status < 300 ? resolve() : reject(new Error(`Storage refused the upload (${xhr.status})`)));
    xhr.onerror = () => reject(new Error("The upload was interrupted. Check your connection and try again."));
    xhr.send(file);
  });
}

/** Upload a file; resolves to {url, path, size, content_type}. onProgress gets 0–100. */
export async function uploadFile(file, { onProgress } = {}) {
  const m = await mode();
  const type = file.type || "application/octet-stream";
  if (m.max_mb && file.size > m.max_mb * 1024 * 1024) throw new Error(`File is over the ${m.max_mb} MB limit`);
  if (m.direct) {
    const { data: ticket } = await api.post("/storage/upload-url", { filename: file.name, content_type: type, size: file.size });
    await putWithProgress(ticket.put_url, file, ticket.headers, onProgress);
    const { data } = await api.post("/storage/complete", { file_id: ticket.file_id });
    return data;
  }
  const fd = new FormData();
  fd.append("file", file);
  const { data } = await api.post("/storage/upload", fd, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (e) => onProgress?.(e.total ? Math.round((e.loaded / e.total) * 100) : 0),
  });
  return data;
}

export function uploadError(err) {
  return err?.response?.data?.detail || err?.message || "Upload failed";
}
