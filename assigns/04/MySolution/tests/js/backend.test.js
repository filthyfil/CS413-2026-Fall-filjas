// HttpBackend with a fake fetch: request shape and error mapping.
import test from "node:test";
import assert from "node:assert/strict";

import { HttpBackend } from "../../web/js/backend.js";

const json = (status, body) => ({
  status, statusText: "", json: async () => body,
});

test("posts JSON to /api/<op> and returns the server result", async () => {
  const seen = [];
  const backend = new HttpBackend({ fetchImpl: async (url, init) => {
    seen.push([url, init.method, JSON.parse(init.body)]);
    return json(200, { op: "lint", revision: 3, status: "ok", message: "m",
      errorKind: null, value: null, details: {} });
  } });
  const r = await backend.lint({ source: "S", revision: 3 });
  assert.equal(r.status, "ok");
  assert.deepEqual(seen, [["/api/lint", "POST", { source: "S", revision: 3 }]]);
});

test("non-JSON server errors and network errors become failures", async () => {
  const b1 = new HttpBackend({ fetchImpl: async () => ({ status: 502, statusText: "Bad Gateway",
    json: async () => { throw new SyntaxError("not json"); } }) });
  const r1 = await b1.lint({ source: "S", revision: 1 });
  assert.deepEqual([r1.status, r1.errorKind, r1.revision, r1.op], ["failure", "backend", 1, "lint"]);
  assert.match(r1.message, /502/);

  const b2 = new HttpBackend({ fetchImpl: async () => { throw new TypeError("Failed to fetch"); } });
  const r2 = await b2.interpret({ source: "S", revision: 2, runId: "x" });
  assert.equal(r2.status, "failure");
  assert.match(r2.message, /Could not reach the server/);
});

test("cancel posts the run id and aborts the pending request", async () => {
  const urls = [];
  const backend = new HttpBackend({ fetchImpl: (url, init) => {
    urls.push(url);
    if (url.endsWith("/cancel")) return Promise.resolve(json(200, { cancelled: true }));
    return new Promise((_, reject) => {      // a server that never answers
      init.signal.addEventListener("abort", () => reject(new Error("aborted")));
    });
  } });
  const running = backend.interpret({ source: "S", revision: 4, runId: "r9" });
  await backend.cancel({ runId: "r9" });
  const r = await running;
  assert.deepEqual([r.status, r.revision], ["cancelled", 4]);
  assert.deepEqual(urls, ["/api/interpret", "/api/cancel"]);
});
