// Controller: turns user intentions (forwarded by the View) into Model
// updates and backend calls. It never touches the DOM.

import { failureResult } from "./backend.js";
import { MAX_SOURCE_BYTES } from "./model.js";

let runCounter = 0;
const defaultRunId = () =>
  `run-${Date.now().toString(36)}-${(runCounter += 1)}`;

export class AppController {
  constructor(model, backend, { examples = {}, newRunId = defaultRunId } = {}) {
    this.model = model;
    this.backend = backend;
    this.examples = examples;     // key -> {name, text}
    this.newRunId = newRunId;
  }

  // ---- Load source menu ------------------------------------------------

  manualInput() {
    return this.model.openManualInput();
  }

  loadExample(key) {
    const example = this.examples[key];
    if (!example) return this.model.rejectSource(`Unknown example: ${key}.`);
    return this.model.loadSource(example.name, example.text);
  }

  // `file` is anything with name, size and arrayBuffer() (a browser File).
  async uploadFile(file) {
    const model = this.model;
    if (!model.canReplaceSource) {
      return model.rejectSource("Apply or discard your changes (and wait for " +
        "any running action) before loading another source.");
    }
    if (file.size > MAX_SOURCE_BYTES) {
      return model.rejectSource(`${file.name} was not loaded: it is ` +
        `${file.size} bytes; the limit is ${MAX_SOURCE_BYTES} bytes.`);
    }
    let text;
    try {
      const bytes = await file.arrayBuffer();
      text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
    } catch {
      return model.rejectSource(`${file.name} was not loaded: it is not ` +
        "valid UTF-8 text.");
    }
    return model.loadSource(file.name, text);
  }

  // ---- editor ----------------------------------------------------------

  edit(text) {
    return this.model.editDraft(text);
  }

  apply() {
    return this.model.applyDraft();
  }

  discard() {
    return this.model.discardDraft();
  }

  // ---- operations ------------------------------------------------------

  async run(op) {
    const model = this.model;
    const runId = this.newRunId();
    const started = model.beginOperation(op, runId);
    if (!started.ok) return started;
    const { revision } = model.busy;
    const request = op === "execute"
      ? { artifact: model.artifact, revision }
      : { source: model.applied.text, revision, runId };
    let result;
    try {
      result = await this.backend[op](request);
    } catch (err) {
      result = failureResult(op, revision,
        `Backend error: ${err?.message ?? err}`);
    }
    if (!result || typeof result !== "object") {
      result = failureResult(op, revision, "Backend returned no result.");
    }
    return model.completeOperation(result);
  }

  async stop() {
    const busy = this.model.busy;
    if (!busy || !this.model.markStopping().ok) return;
    try {
      await this.backend.cancel({ runId: busy.runId });
    } catch {
      // The pending run() still finishes with a result of its own.
    }
  }

  retry() {
    const op = this.model.retryOp;
    return op ? this.run(op) : Promise.resolve({ ok: false, reason: "Nothing to retry." });
  }
}
