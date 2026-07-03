// File download helpers.

export function downloadBlob(data: BlobPart, filename: string, mime: string): void {
  const blob = new Blob([data], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  // Revoke on the next tick so the download has time to start.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function downloadText(text: string, filename: string, mime = "text/plain"): void {
  downloadBlob(text, filename, mime);
}

export function downloadJson(obj: unknown, filename: string): void {
  downloadBlob(JSON.stringify(obj, null, 2), filename, "application/json");
}

export function downloadBytes(bytes: Uint8Array, filename: string, mime: string): void {
  // Copy into a fresh ArrayBuffer-backed Uint8Array to satisfy BlobPart typing
  // across environments (avoids SharedArrayBuffer-backed view issues).
  const copy = new Uint8Array(bytes.length);
  copy.set(bytes);
  downloadBlob(copy, filename, mime);
}
