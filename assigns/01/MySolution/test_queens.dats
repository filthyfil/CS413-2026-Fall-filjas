(*
** test_queens.dats -- test driver for the top-level functions of
** [eight_queens.dats].
**
** The define below suppresses the [main0] of the included file so this
** driver can supply its own entry point.  It MUST precede the #include.
**
** Build: patscc -DATS_MEMALLOC_LIBC -o test_queens test_queens.dats
*)

#define EIGHT_QUEENS_NO_MAIN 1
#include "./eight_queens.dats"

(* ****** ****** *)
//
// A test suite must run every case and then report; [assertloc] cannot be
// used because it is [assert_errmsg], which does fprintf(stderr) + exit(1)
// on the first failure.  So thread a (ntest, nfail) accumulator instead --
// the same shadowed-[val] idiom [board_set] uses.
//
typedef stat = (int, int) // (ntest, nfail)

//
// ATS prints bools as [true]/[false] but Python prints [True]/[False];
// funnel every bool through this so the two outputs can be diffed.
//
fun b2i (b: bool): int = if b then 1 else 0

//
// [fprint_tup] is only defined for arities 2-4, so an [int8] cannot be
// printed in one call.  Hand-write it, in a shape Python can match exactly.
//
fun print_int8 (bd: int8): void =
(
  print! ("(", bd.0, ",", bd.1, ",", bd.2, ",", bd.3,
          ",", bd.4, ",", bd.5, ",", bd.6, ",", bd.7, ")")
) // end of [print_int8]

fun board_eq (a: int8, b: int8): bool =
(
  a.0 = b.0 andalso a.1 = b.1 andalso a.2 = b.2 andalso a.3 = b.3
  andalso
  a.4 = b.4 andalso a.5 = b.5 andalso a.6 = b.6 andalso a.7 = b.7
) // end of [board_eq]

(* ****** ****** *)

fun assert_eq_int
  (st: stat, name: string, expected: int, actual: int): stat =
  if expected = actual
    then let
      val () = print! ("## PASS ", name, " = ", actual, "\n")
    in
      (st.0 + 1, st.1)
    end // end of [then]
    else let
      val () = print! ("## FAIL ", name, ": expected ", expected,
                       ", got ", actual, "\n")
    in
      (st.0 + 1, st.1 + 1)
    end // end of [else]
// end of [assert_eq_int]

fun assert_eq_bool
  (st: stat, name: string, expected: bool, actual: bool): stat =
  assert_eq_int (st, name, b2i (expected), b2i (actual))
// end of [assert_eq_bool]

fun assert_eq_board
  (st: stat, name: string, expected: int8, actual: int8): stat =
  if board_eq (expected, actual)
    then let
      val () = print! ("## PASS ", name, " = ")
      val () = print_int8 (actual)
      val () = print "\n"
    in
      (st.0 + 1, st.1)
    end // end of [then]
    else let
      val () = print! ("## FAIL ", name, ": expected ")
      val () = print_int8 (expected)
      val () = print ", got "
      val () = print_int8 (actual)
      val () = print "\n"
    in
      (st.0 + 1, st.1 + 1)
    end // end of [else]
// end of [assert_eq_board]

(* ****** ****** *)

#define BDID (0, 1, 2, 3, 4, 5, 6, 7) // identity board, for indexing tests
#define BDZ  (0, 0, 0, 0, 0, 0, 0, 0) // the seed board used by main0

(* ****** ****** *)
//
// T1: board_get -- normal indices
//
fun test_board_get_normal (st: stat): stat = let
  val bd = BDID: int8
  val st = assert_eq_int (st, "board_get/0", 0, board_get (bd, 0))
  val st = assert_eq_int (st, "board_get/3", 3, board_get (bd, 3))
  val st = assert_eq_int (st, "board_get/7", 7, board_get (bd, 7))
in
  st
end // end of [test_board_get_normal]

//
// T2: board_get -- out of range yields the ~1 sentinel
//
fun test_board_get_range (st: stat): stat = let
  val bd = BDID: int8
  val st = assert_eq_int (st, "board_get/neg1", ~1, board_get (bd, ~1))
  val st = assert_eq_int (st, "board_get/8", ~1, board_get (bd, 8))
  val st = assert_eq_int (st, "board_get/99", ~1, board_get (bd, 99))
in
  st
end // end of [test_board_get_range]

//
// T3: board_set -- normal update, and that it does not disturb other rows
//
fun test_board_set_normal (st: stat): stat = let
  val bd = BDZ: int8
  val st = assert_eq_board
    (st, "board_set/0", (9,0,0,0,0,0,0,0), board_set (bd, 0, 9))
  val st = assert_eq_board
    (st, "board_set/7", (0,0,0,0,0,0,0,9), board_set (bd, 7, 9))
  val st = assert_eq_board
    (st, "board_set/mid", (0,1,2,9,4,5,6,7), board_set (BDID, 3, 9))
in
  st
end // end of [test_board_set_normal]

//
// T4: board_set -- out of range is a SILENT no-op (no error is signalled)
//
fun test_board_set_range (st: stat): stat = let
  val bd = BDID: int8
  val st = assert_eq_board (st, "board_set/neg1", bd, board_set (bd, ~1, 9))
  val st = assert_eq_board (st, "board_set/8", bd, board_set (bd, 8, 9))
in
  st
end // end of [test_board_set_range]

//
// T5: safety_test1 -- the three ways two queens conflict, and the safe case
//
fun test_safety_test1 (st: stat): stat = let
  val st = assert_eq_bool (st, "st1/safe", true, safety_test1 (0, 0, 1, 2))
  val st = assert_eq_bool (st, "st1/samecol", false, safety_test1 (0, 3, 5, 3))
  val st = assert_eq_bool (st, "st1/diag", false, safety_test1 (0, 0, 3, 3))
  val st = assert_eq_bool (st, "st1/antidiag", false, safety_test1 (0, 3, 3, 0))
//
// A queen is not "safe" from itself: [j0 != j1] fails.  Harmless here only
// because search always calls safety_test2 with rows STRICTLY below i.
//
  val st = assert_eq_bool (st, "st1/self", false, safety_test1 (3, 3, 3, 3))
//
// Same row is never tested -- one queen per row is structural, not checked.
//
  val st = assert_eq_bool (st, "st1/samerow", true, safety_test1 (4, 0, 4, 2))
in
  st
end // end of [test_safety_test1]

//
// T6: safety_test2 -- the empty-prefix base case and short-circuiting
//
fun test_safety_test2 (st: stat): stat = let
  val bd = (0, 4, 7, 5, 2, 6, 1, 3): int8 // solution #1
  val st = assert_eq_bool (st, "st2/empty", true, safety_test2 (0, 0, bd, ~1))
  val st = assert_eq_bool (st, "st2/deepneg", true, safety_test2 (0, 0, bd, ~5))
//
// Row 3 of solution #1 is column 5; (4,5) shares that column.
//
  val st = assert_eq_bool (st, "st2/conflict", false, safety_test2 (4, 5, bd, 3))
  val st = assert_eq_bool (st, "st2/ok", true, safety_test2 (4, 2, bd, 3))
in
  st
end // end of [test_safety_test2]

//
// T7: search -- the whole puzzle, and the j >= N entry with no room to
// backtrack (i = 0), which must return the accumulator untouched.
//
fun test_search_basic (st: stat): stat = let
  val st = assert_eq_int (st, "search/total", 92, search (BDZ, 0, 0, 0))
  val st = assert_eq_int (st, "search/jN", 0, search (BDZ, 0, 8, 0))
  val st = assert_eq_int (st, "search/jbig", 0, search (BDZ, 0, 99, 0))
in
  st
end // end of [test_search_basic]

//
// T8: nsol is a pure pass-through accumulator -- seeding it just offsets
// the result, proving nothing is added on the way back up the call chain.
//
fun test_search_accum (st: stat): stat = let
  val st = assert_eq_int (st, "search/seed5", 97, search (BDZ, 0, 0, 5))
  val st = assert_eq_int (st, "search/seed100", 192, search (BDZ, 0, 0, 100))
in
  st
end // end of [test_search_accum]

//
// T9: seeding row 0 and resuming at row 1.  Because the backtrack branch
// has no floor, this does NOT count completions of the prefix -- it counts
// every solution whose row-0 queen sits in column >= c.  The successive
// differences are the per-column counts 4,8,16,18,18,16,8,4 (sum 92, and
// mirror-symmetric), which is an oracle independent of the program itself.
//
fun test_search_resume (st: stat): stat = let
  fun seed (c: int): int = search (board_set (BDZ, 0, c), 1, 0, 0)
  val st = assert_eq_int (st, "search/col0", 92, seed (0))
  val st = assert_eq_int (st, "search/col1", 88, seed (1))
  val st = assert_eq_int (st, "search/col2", 80, seed (2))
  val st = assert_eq_int (st, "search/col3", 64, seed (3))
  val st = assert_eq_int (st, "search/col4", 46, seed (4))
  val st = assert_eq_int (st, "search/col5", 28, seed (5))
  val st = assert_eq_int (st, "search/col6", 12, seed (6))
  val st = assert_eq_int (st, "search/col7", 4, seed (7))
//
// Per-column counts, as differences.  Mirror symmetry d[c] = d[7-c].
//
  val st = assert_eq_int (st, "search/diff0", 4, seed (0) - seed (1))
  val st = assert_eq_int (st, "search/diff3", 18, seed (3) - seed (4))
  val st = assert_eq_int (st, "search/mirror0", 0,
    (seed (0) - seed (1)) - seed (7))
  val st = assert_eq_int (st, "search/mirror1", 0,
    (seed (1) - seed (2)) - (seed (6) - seed (7)))
  val st = assert_eq_int (st, "search/mirror3", 0,
    (seed (3) - seed (4)) - (seed (4) - seed (5)))
in
  st
end // end of [test_search_resume]

//
// T10: CHARACTERIZATION of a defect.  search never re-validates the rows it
// is handed; safety_test2 only checks a NEW candidate against rows below it.
// Seeding the illegal prefix (0,1) -- two queens on a diagonal -- therefore
// yields 96: the 92 real solutions plus 4 fabricated boards.  This test
// pins the buggy behaviour so a future fix is visible as a failure here.
//
fun test_search_badprefix (st: stat): stat = let
  val st = assert_eq_int
    (st, "search/badprefix01", 96, search ((0,1,0,0,0,0,0,0), 2, 0, 0))
  val st = assert_eq_int
    (st, "search/badprefix00", 98, search ((0,0,0,0,0,0,0,0), 2, 0, 0))
in
  st
end // end of [test_search_badprefix]

//
// T11: i >= N is unguarded.  board_set silently ignores the write, so the
// row counter can run away.  i = 8 returns a nonsense count; i = 9 does not
// terminate at all and is therefore NOT exercised here (see TEST-RESULTS.md).
//
fun test_search_bigrow (st: stat): stat = let
  val st = assert_eq_int (st, "search/i8", 101, search (BDZ, 8, 0, 0))
in
  st
end // end of [test_search_bigrow]

(* ****** ****** *)

implement
main1 (): int = let
//
val st = (0, 0): stat
//
val st = test_board_get_normal (st)
val st = test_board_get_range (st)
val st = test_board_set_normal (st)
val st = test_board_set_range (st)
val st = test_safety_test1 (st)
val st = test_safety_test2 (st)
val st = test_search_basic (st)
val st = test_search_accum (st)
val st = test_search_resume (st)
val st = test_search_badprefix (st)
val st = test_search_bigrow (st)
//
val () = print! ("## TOTAL ", st.0, " tests, ", st.1, " failure(s)\n")
//
in
  if st.1 = 0 then 0 else 1
end // end of [main1]

(* ****** ****** *)

(* end of [test_queens.dats] *)
