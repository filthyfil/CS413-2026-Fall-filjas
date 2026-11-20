// Transport layer: JSON-RPC 2.0 over fetch, plus the four queens methods.
// Knows nothing about the board or playback. Every failure is thrown as an
// RpcError whose `kind` tells the UI what went wrong:
//   network  - server unreachable or request timed out
//   http     - non-200 HTTP status
//   protocol - response is not a well-formed JSON-RPC reply for our request
//   rpc      - a JSON-RPC error object (code/message/data from the server)

export const STREAM_NOT_FOUND = -32001;

export class RpcError extends Error {
  constructor(message, { kind, code = null, data = null, status = null } = {}) {
    super(message);
    this.name = "RpcError";
    this.kind = kind;
    this.code = code;
    this.data = data;
    this.status = status;
  }
}

export class RpcClient {
  constructor({ url = "/rpc", fetchImpl = (...a) => globalThis.fetch(...a), timeoutMs = 15000 } = {}) {
    this.url = url;
    this.fetch = fetchImpl;
    this.timeoutMs = timeoutMs;
    this.nextId = 0;
  }

  async call(method, params) {
    const id = ++this.nextId;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    let response;
    try {
      response = await this.fetch(this.url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jsonrpc: "2.0", method, params, id }),
        signal: controller.signal,
      });
    } catch (error) {
      const timedOut = error && error.name === "AbortError";
      throw new RpcError(timedOut ? "Request timed out" : "Network error: cannot reach the server",
        { kind: "network" });
    } finally {
      clearTimeout(timer);
    }
    if (response.status !== 200) {
      throw new RpcError(`Server returned HTTP ${response.status}`, { kind: "http", status: response.status });
    }
    let body;
    try {
      body = await response.json();
    } catch {
      throw new RpcError("Malformed response from server", { kind: "protocol" });
    }
    if (!body || typeof body !== "object" || body.jsonrpc !== "2.0" || body.id !== id) {
      throw new RpcError("Unexpected response from server", { kind: "protocol" });
    }
    if (body.error) {
      const { code = null, message = "RPC error", data = null } = body.error;
      throw new RpcError(message, { kind: "rpc", code, data });
    }
    if (!("result" in body)) {
      throw new RpcError("Response has no result", { kind: "protocol" });
    }
    return body.result;
  }
}

// The queens methods, with light checks on result shapes so a bad reply
// surfaces as an error instead of a corrupted animation.
export class QueensApi {
  constructor(rpc = new RpcClient()) {
    this.rpc = rpc;
  }

  health() {
    return this.rpc.call("service.health", {});
  }

  async open(size) {
    const result = await this.rpc.call("queens.open", { size });
    if (typeof result?.stream_id !== "string") {
      throw new RpcError("Unexpected queens.open result", { kind: "protocol" });
    }
    return result;
  }

  async next(streamId, limit) {
    const result = await this.rpc.call("queens.next", { stream_id: streamId, limit });
    if (!Array.isArray(result?.events) || typeof result.done !== "boolean" || result.events.length > limit) {
      throw new RpcError("Unexpected queens.next result", { kind: "protocol" });
    }
    return result;
  }

  close(streamId) {
    return this.rpc.call("queens.close", { stream_id: streamId });
  }

  // Best-effort release while the page unloads. A notification needs no reply,
  // and keepalive lets the request outlive the page.
  closeOnUnload(streamId) {
    try {
      globalThis.fetch(this.rpc.url, {
        method: "POST",
        keepalive: true,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jsonrpc: "2.0", method: "queens.close", params: { stream_id: streamId } }),
      }).catch(() => {});
    } catch {
      /* page is going away; the server-side TTL cleans up */
    }
  }
}
