// View: renders the Model into the page and forwards user actions to the
// Controller. It contains no language logic and never changes the Model
// directly. All program text is inserted with textContent / value, so
// HTML-like source or output is shown literally.

import { OPERATIONS } from "./model.js";

export const OP_LABELS = {
  lint: "Lint",
  interpret: "Interpret",
  typecheck: "Type-check",
  compile: "Compile",
  execute: "Execute",
};

export function outcomeLabel(result) {
  switch (result.status) {
    case "ok": return "Success";
    case "error": return result.errorKind
      ? `Error (${result.errorKind === "language" ? "undeclared variables"
        : result.errorKind})` : "Error";
    case "failure": return "Backend failure";
    case "not_implemented": return "Not implemented";
    case "cancelled": return "Stopped";
    default: return result.status;
  }
}

export class AppView {
  constructor(doc, model, controller) {
    this.doc = doc;
    this.model = model;
    this.controller = controller;
    const $ = (id) => doc.getElementById(id);
    this.el = {
      main: $("app"),
      fileInput: $("file-input"),
      manual: $("manual-btn"),
      examples: [...doc.querySelectorAll("[data-example]")],
      sourceInfo: $("source-info"),
      editor: $("editor"),
      editState: $("edit-state"),
      apply: $("apply-btn"),
      discard: $("discard-btn"),
      ops: Object.fromEntries(OPERATIONS.map((op) => [op, $(`op-${op}`)])),
      actionHint: $("action-hint"),
      executeNote: $("execute-note"),
      stop: $("stop-btn"),
      retry: $("retry-btn"),
      status: $("status"),
      notice: $("notice"),
      results: $("results"),
      clear: $("clear-btn"),
    };
    this.#bind();
    model.subscribe(() => this.render());
    this.render();
  }

  #bind() {
    const { el, controller } = this;
    el.fileInput.addEventListener("change", async () => {
      const file = el.fileInput.files[0];
      el.fileInput.value = "";   // allow choosing the same file again
      if (file) await controller.uploadFile(file);
    });
    el.manual.addEventListener("click", () => {
      controller.manualInput();
      el.editor.focus();
    });
    for (const button of el.examples) {
      button.addEventListener("click", () => controller.loadExample(button.dataset.example));
    }
    el.editor.addEventListener("input", () => controller.edit(el.editor.value));
    el.apply.addEventListener("click", () => controller.apply());
    el.discard.addEventListener("click", () => controller.discard());
    for (const [op, button] of Object.entries(el.ops)) {
      button.addEventListener("click", () => controller.run(op));
    }
    el.stop.addEventListener("click", () => controller.stop());
    el.retry.addEventListener("click", () => controller.retry());
    el.clear.addEventListener("click", () => controller.clearResults());
  }

  render() {
    const { model: m, el } = this;
    const busy = m.busy;

    // Load source menu
    el.fileInput.disabled = !m.canReplaceSource;
    el.manual.disabled = !m.canReplaceSource;
    for (const button of el.examples) button.disabled = !m.canReplaceSource;
    el.sourceInfo.textContent = m.applied
      ? `Applied source: ${m.applied.name} — revision ${m.applied.revision}`
      : "No source applied yet.";

    // Editor
    el.editor.disabled = m.draft === null;
    el.editor.readOnly = !m.canEdit;
    const text = m.draft?.text ?? "";
    if (el.editor.value !== text) el.editor.value = text;
    el.apply.disabled = !m.canApply;
    el.discard.disabled = !m.canDiscard;
    el.editState.textContent = m.draft === null
      ? "Choose Manual input, a canned example or a file to start editing."
      : m.hasUnappliedEdits ? `Editing ${m.draft.name}: unapplied changes.`
        : m.inSync ? `Editor shows revision ${m.applied.revision}.`
          : `Editing ${m.draft.name}: not applied yet.`;

    // Actions
    for (const [op, button] of Object.entries(el.ops)) {
      const reason = m.blockedReason(op);
      button.disabled = reason !== null;
      button.title = reason ?? `Run ${OP_LABELS[op]} on revision ${m.applied?.revision}`;
    }
    const general = busy ? null : m.blockedReason("lint");
    el.actionHint.textContent = general ?? "";
    el.executeNote.textContent = m.hasCurrentArtifact ? ""
      : m.blockedReason("execute") ?? "";
    el.stop.disabled = !(busy && busy.op === "interpret" && !busy.stopping);
    el.retry.hidden = !m.retryOp;
    el.retry.disabled = !(m.retryOp && m.canRun(m.retryOp));
    el.retry.textContent = m.retryOp ? `Retry ${OP_LABELS[m.retryOp]}` : "Retry";

    // Status (text, not only color)
    el.main.setAttribute("aria-busy", busy ? "true" : "false");
    el.status.dataset.state = busy ? "busy" : "idle";
    el.status.textContent = !busy ? "Status: ready."
      : busy.stopping ? `Status: stopping ${OP_LABELS[busy.op]}…`
        : `Status: busy — ${OP_LABELS[busy.op]} is running on revision ${busy.revision}…`;
    el.notice.hidden = m.notice === null;
    el.notice.dataset.kind = m.notice?.kind ?? "";
    el.notice.textContent = m.notice
      ? `${m.notice.kind === "error" ? "Error" : "Note"}: ${m.notice.text}` : "";

    el.clear.disabled = !m.canClearResults;
    this.#renderResults();
  }

  #renderResults() {
    const { doc, el, model } = this;
    const items = model.results.map((result) => {
      const li = doc.createElement("li");
      li.className = "result";
      li.dataset.status = result.status;
      const head = doc.createElement("h3");
      head.textContent = `${OP_LABELS[result.op] ?? result.op} · revision ` +
        `${result.revision} · ${outcomeLabel(result)}`;
      const message = doc.createElement("pre");
      message.textContent = result.message;
      li.append(head, message);
      if (result.value !== null && result.value !== undefined) {
        const value = doc.createElement("pre");
        value.className = "value";
        value.textContent = result.value;
        li.append(value);
      }
      return li;
    });
    if (items.length === 0) {
      const li = doc.createElement("li");
      li.className = "empty";
      li.textContent = "No results for this revision yet.";
      items.push(li);
    }
    el.results.replaceChildren(...items);
  }
}
