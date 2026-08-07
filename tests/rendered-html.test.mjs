import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);
  return worker.fetch(
    new Request("http://localhost/", { headers: { accept: "text/html" } }),
    { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } },
    { waitUntil() {}, passThroughOnException() {} },
  );
}

test("renders the DICOM Flow operational shell", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);
  const html = await response.text();
  assert.match(html, /DICOM Flow/);
  assert.match(html, /CENTRO DE OPERACIONES/);
  assert.match(html, /Cargando información clínica/);
  assert.doesNotMatch(html, /Your site is taking shape/);
});

test("connects patient and conversion workflows to the backend proxy", async () => {
  const [page, proxy, api] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/api/backend/[...path]/route.ts", import.meta.url), "utf8"),
    readFile(new URL("../services/api/main.py", import.meta.url), "utf8"),
  ]);
  assert.match(page, /api<\{ patients: Patient\[\] \}>\("v1\/patients"\)/);
  assert.match(page, /api<\{ batch_id: string \}>\("v1\/conversions"/);
  assert.match(proxy, /process\.env\.API_URL/);
  assert.match(api, /@app\.post\("\/v1\/patients"/);
  assert.match(api, /@app\.post\("\/v1\/conversions"/);
  assert.match(api, /@app\.get\("\/v1\/dashboard"/);
});
