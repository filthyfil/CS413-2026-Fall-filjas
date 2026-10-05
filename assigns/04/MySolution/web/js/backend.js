// Backend interface (language-tool adapter) and its HTTP implementation.
//
// Any object with these async methods can be passed to the Controller:
//
//   lint({source, revision})             -> Result
//   interpret({source, revision, runId}) -> Result
//   typecheck({source, revision})        -> Result   (placeholder)
//   compile({source, revision})          -> Result   (placeholder)
//   execute({artifact, revision})        -> Result
//   cancel({runId})                      -> void     (stop a running interpret)
//
// Result = {op, revision, status, message, errorKind, value, details}
//   status:    "ok" | "error" | "failure" | "not_implemented" | "cancelled"
//   errorKind: "input" | "language" | "runtime" | "backend" | null
// A method must resolve to a Result; it should not throw. The Controller
// still guards against throwing backends.

export const STATUSES = ["ok", "error", "failure", "not_implemented", "cancelled"];

export function makeResult(op, revision, status, message,
                           { errorKind = null, value = null, details = {} } = {}) {
  return { op, revision, status, message, errorKind, value, details };
}

export function failureResult(op, revision, message) {
  return makeResult(op, revision, "failure", message, { errorKind: "backend" });
}

export class HttpBackend {
  constructor({ baseUrl = "", fetchImpl = globalThis.fetch.bind(globalThis) } = {}) {
    this.baseUrl = baseUrl;
    this.fetch = fetchImpl;
    this.pending = new Map();   // runId -> AbortController
  }

  lint({ source, revision }) {
    return this.#call("lint", revision, { source, revision });
  }

  interpret({ source, revision, runId }) {
    return this.#call("interpret", revision, { source, revision, runId }, runId);
  }

  typecheck({ source, revision }) {
    return this.#call("typecheck", revision, { source, revision });
  }

  compile({ source, revision }) {
    return this.#call("compile", revision, { source, revision });
  }

  execute({ artifact, revision }) {
    return this.#call("execute", revision, { artifact, revision });
  }

  async cancel({ runId }) {
    try {
      await this.fetch(`${this.baseUrl}/api/cancel`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ runId }),
      });
    } finally {
      // Stop waiting even if the server never answers the original request.
      this.pending.get(runId)?.abort();
    }
  }

  async #call(op, revision, payload, runId = null) {
    const abort = new AbortController();
    if (runId) this.pending.set(runId, abort);
    try {
      const response = await this.fetch(`${this.baseUrl}/api/${op}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: abort.signal,
      });
      let body = null;
      try {
        body = await response.json();
      } catch {
        // not JSON: handled below
      }
      if (body && STATUSES.includes(body.status)) return body;
      return failureResult(op, revision,
        `Server error: HTTP ${response.status} ${response.statusText || ""}`.trim());
    } catch (err) {
      if (abort.signal.aborted) {
        return makeResult(op, revision, "cancelled",
          "Interpretation was stopped by the user.");
      }
      return failureResult(op, revision,
        `Could not reach the server: ${err?.message ?? err}`);
    } finally {
      if (runId) this.pending.delete(runId);
    }
  }
}
