import { test } from "node:test";
import assert from "node:assert/strict";

import { QueensApi, RpcClient, RpcError } from "../../client/rpc.js";

// A fetch double: `reply(request)` returns {status, body} or throws.
function fakeFetch(reply) {
  const requests = [];
  const impl = async (url, init) => {
    const req = JSON.parse(init.body);
    requests.push({ url, init, req });
    const { status = 200, body, raw } = await reply(req, init);
    return { status, json: async () => (raw !== undefined ? JSON.parse(raw) : body) };
  };
  return { impl, requests };
}

const ok = (result) => (req) => ({ body: { jsonrpc: "2.0", result, id: req.id } });

test("sends a JSON-RPC 2.0 POST with increasing ids", async () => {
  const f = fakeFetch((req) => ok(req.method === "queens.open" ? { stream_id: "s1", size: 8 } : { status: "ok", version: "1.0" })(req));
  const api = new QueensApi(new RpcClient({ url: "/rpc", fetchImpl: f.impl }));
  await api.health();
  await api.open(8);
  assert.equal(f.requests[0].init.method, "POST");
  assert.equal(f.requests[0].init.headers["Content-Type"], "application/json");
  assert.deepEqual(f.requests.map((r) => r.req.id), [1, 2]);
  assert.deepEqual(f.requests[1].req, { jsonrpc: "2.0", method: "queens.open", params: { size: 8 }, id: 2 });
});

test("maps a JSON-RPC error object to kind rpc", async () => {
  const f = fakeFetch((req) => ({ body: { jsonrpc: "2.0", id: req.id,
    error: { code: -32001, message: "Unknown stream", data: { stream_id: "x" } } } }));
  const api = new QueensApi(new RpcClient({ fetchImpl: f.impl }));
  await assert.rejects(api.next("x", 1), (e) => e instanceof RpcError && e.kind === "rpc" && e.code === -32001);
});

test("network failure, HTTP status, and malformed replies are distinct kinds", async () => {
  const rpc = (reply) => new RpcClient({ fetchImpl: fakeFetch(reply).impl });
  await assert.rejects(rpc(() => { throw new TypeError("Failed to fetch"); }).call("m", {}), { kind: "network" });
  await assert.rejects(rpc(() => ({ status: 500, body: {} })).call("m", {}), { kind: "http", status: 500 });
  await assert.rejects(rpc(() => ({ raw: "<html>" })).call("m", {}), { kind: "protocol" });
  await assert.rejects(rpc(() => ({ body: { jsonrpc: "2.0", result: 1, id: 999 } })).call("m", {}), { kind: "protocol" });
  await assert.rejects(rpc((req) => ({ body: { jsonrpc: "2.0", id: req.id } })).call("m", {}), { kind: "protocol" });
});

test("times out a hung request", async () => {
  const hang = (url, init) => new Promise((_, reject) => {
    init.signal.addEventListener("abort", () => reject(Object.assign(new Error("aborted"), { name: "AbortError" })));
  });
  const rpc = new RpcClient({ fetchImpl: hang, timeoutMs: 20 });
  await assert.rejects(rpc.call("m", {}), { kind: "network", message: "Request timed out" });
});

test("rejects a next result with more events than requested", async () => {
  const f = fakeFetch(ok({ events: [{}, {}], done: false }));
  const api = new QueensApi(new RpcClient({ fetchImpl: f.impl }));
  await assert.rejects(api.next("s", 1), { kind: "protocol" });
});
