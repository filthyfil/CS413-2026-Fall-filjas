// Board renderer: draws an event's board snapshot plus highlights for that
// event. Each event carries a full board, so the view never has to replay
// history. Rendering any event on its own is always correct.

import { attackPath, conflicts } from "./events.js";

const QUEEN = "♛";

export class BoardView {
  constructor(root) {
    this.root = root;
    this.size = 0;
    this.cells = [];
  }

  setSize(size) {
    if (size === this.size) return this.clear();
    this.size = size;
    this.root.style.setProperty("--n", size);
    this.root.replaceChildren();
    this.cells = [];

    const corner = document.createElement("div");
    corner.className = "label corner";
    this.root.append(corner);
    for (let c = 0; c < size; c++) this.root.append(this._label(c, "col-label"));
    for (let r = 0; r < size; r++) {
      this.root.append(this._label(r, "row-label"));
      const row = [];
      for (let c = 0; c < size; c++) {
        const cell = document.createElement("div");
        cell.className = `cell ${(r + c) % 2 ? "dark" : "light"}`;
        cell.dataset.row = r;
        cell.dataset.col = c;
        this.root.append(cell);
        row.push(cell);
      }
      this.cells.push(row);
    }
    this.clear();
  }

  _label(n, cls) {
    const el = document.createElement("div");
    el.className = `label ${cls}`;
    el.textContent = n;
    return el;
  }

  _baseClass(r, c) {
    return `cell ${(r + c) % 2 ? "dark" : "light"}`;
  }

  clear() {
    this.root.classList.remove("is-solution", "is-done");
    for (let r = 0; r < this.size; r++) {
      for (let c = 0; c < this.size; c++) {
        const cell = this.cells[r][c];
        cell.className = this._baseClass(r, c);
        cell.textContent = "";
        cell.removeAttribute("title");
      }
    }
  }

  _cell(row, column) {
    return this.cells[row]?.[column];
  }

  _mark(row, column, ...classes) {
    this._cell(row, column)?.classList.add(...classes);
  }

  _queens(board) {
    board.forEach((column, row) => {
      const cell = this._cell(row, column);
      if (!cell) return;
      cell.textContent = QUEEN;
      cell.classList.add("queen");
    });
  }

  render(event) {
    this.clear();
    if (!event) return;
    const { row, column } = event;
    if (event.board) this._queens(event.board);
    if (typeof row === "number") {
      for (let c = 0; c < this.size; c++) this._mark(row, c, "active-row");
    }

    switch (event.event) {
      case "try":
        this._ghost(row, column, "cand-try");
        break;
      case "place":
        this._mark(row, column, "cand-place");
        break;
      case "reject": {
        this._ghost(row, column, "cand-reject");
        for (const hit of conflicts(event.board, row, column)) {
          this._mark(hit.row, hit.column, "attacker");
          for (const p of attackPath(hit, { row, column })) this._mark(p.row, p.column, "attack-path");
        }
        break;
      }
      case "backtrack":
        this._ghost(row, column, "cand-backtrack");
        break;
      case "solution":
        this.root.classList.add("is-solution");
        break;
      case "done":
        this.root.classList.add("is-done");
        break;
    }
  }

  // A candidate square that is not (or no longer) on the board.
  _ghost(row, column, cls) {
    const cell = this._cell(row, column);
    if (!cell) return;
    cell.classList.add("ghost", cls);
    cell.textContent = QUEEN;
  }
}
