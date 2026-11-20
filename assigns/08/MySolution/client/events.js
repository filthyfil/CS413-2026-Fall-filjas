// Pure helpers over the documented event schema. No DOM, no network, so
// they run unchanged in Node tests.
//
// A board is an array of queen columns in row order: board[r] is the column
// of the queen in row r. Rows and columns are zero-based.

export const KINDS = Object.freeze(["try", "place", "reject", "backtrack", "solution", "done"]);

// Earlier queens that attack (row, column), each tagged with the line it
// attacks along.
export function conflicts(board, row, column) {
  const found = [];
  for (let r = 0; r < Math.min(row, board.length); r++) {
    const c = board[r];
    if (c === column) found.push({ row: r, column: c, line: "column" });
    else if (Math.abs(c - column) === row - r) found.push({ row: r, column: c, line: "diagonal" });
  }
  return found;
}

// Cells strictly between two squares on the same column or diagonal.
export function attackPath(from, to) {
  const dr = Math.sign(to.row - from.row);
  const dc = Math.sign(to.column - from.column);
  const cells = [];
  let r = from.row + dr;
  let c = from.column + dc;
  while (r !== to.row || c !== to.column) {
    cells.push({ row: r, column: c });
    r += dr;
    c += dc;
  }
  return cells;
}

const at = (row, column) => `(row ${row}, col ${column})`;

// One human-readable sentence for the status line and event log.
export function describe(event, size) {
  switch (event.event) {
    case "try":
      return `Row ${event.row}: trying column ${event.column}`;
    case "place":
      return `Row ${event.row}: column ${event.column} is safe, queen placed`;
    case "reject": {
      const hits = conflicts(event.board, event.row, event.column);
      const why = hits.length
        ? hits.map((h) => `${h.line} of queen at ${at(h.row, h.column)}`).join("; ")
        : "conflict";
      return `Row ${event.row}: column ${event.column} rejected, on the ${why}`;
    }
    case "backtrack": {
      const nextCol = event.column + 1;
      const then = nextCol < size ? `resume at column ${nextCol}` : `row ${event.row} exhausted`;
      return `Row ${event.row}: branch under column ${event.column} exhausted, remove queen, ${then}`;
    }
    case "solution":
      return `Solution found: [${event.board.join(", ")}]`;
    case "done":
      return "Search complete: no further solutions";
    default:
      return `Unknown event ${String(event.event)}`;
  }
}
