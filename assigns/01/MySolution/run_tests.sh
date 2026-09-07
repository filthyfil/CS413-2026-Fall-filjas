#!/bin/bash
#
# run_tests.sh -- build and test the ATS original and the Python translation.
#
# Four layers:
#   0  the instructor's eight functions are still byte-identical
#   1  both programs build
#   2  whole-program output: ATS vs frozen golden, and ATS vs Python
#   3  per-function suites: ATS vs Python, and vs frozen golden markers
#
# Exits nonzero if any layer fails.  Uses [|| fail=1] rather than [set -e]
# so that one failure does not hide the rest.
#
set -u
cd "$(dirname "$0")" || exit 1

PATSCC=${PATSCC:-patscc}
PYTHON=${PYTHON:-python3}
CF="-DATS_MEMALLOC_LIBC"
fail=0
mkdir -p out

say () { printf '\n=== %s\n' "$1"; }

say "Layer 0: instructor's functions unmodified"
# Everything from [#define N 8] to the end of [search] must still match
# source_code_snippets.txt exactly; only main0 and the include may differ.
RANGE='/^#define N 8$/,/^) (\* end of \[search\] \*)$/p'
sed -n "$RANGE" source_code_snippets.txt > out/orig_range.txt
sed -n "$RANGE" eight_queens.dats      > out/live_range.txt
if diff -u out/orig_range.txt out/live_range.txt; then
  echo "OK: $(wc -l < out/live_range.txt) lines identical"
else
  fail=1
fi

say "Layer 1: build"
$PATSCC $CF -o eight_queens eight_queens.dats || fail=1
$PATSCC $CF -o test_queens  test_queens.dats  || fail=1

say "Layer 2: whole-program output"
./eight_queens          > out/run_ats.txt || fail=1
$PYTHON eight_queens.py > out/run_py.txt  || fail=1
diff -u output_ats.txt out/run_ats.txt > /dev/null \
  && echo "OK: ATS matches frozen golden"      || { echo "FAIL: ATS vs golden"; fail=1; }
diff -u out/run_ats.txt out/run_py.txt > /dev/null \
  && echo "OK: Python matches ATS byte-for-byte" || { echo "FAIL: ATS vs Python"; fail=1; }

say "Layer 3: per-function suites"
./test_queens          > out/unit_ats.txt; rc_ats=$?
$PYTHON test_queens.py > out/unit_py.txt;  rc_py=$?
diff -u out/unit_ats.txt out/unit_py.txt > /dev/null \
  && echo "OK: suites agree byte-for-byte"     || { echo "FAIL: suite outputs differ"; fail=1; }
grep '^## ' out/unit_ats.txt > out/marks_ats.txt
diff -u expected_tests.txt out/marks_ats.txt > /dev/null \
  && echo "OK: markers match frozen golden"    || { echo "FAIL: markers vs golden"; fail=1; }
grep -q '^## FAIL' out/unit_ats.txt && { echo "FAIL: ATS suite reported failures"; fail=1; }
grep -q '^## FAIL' out/unit_py.txt  && { echo "FAIL: Python suite reported failures"; fail=1; }
[ "$rc_ats" -eq 0 ] || { echo "FAIL: test_queens exit=$rc_ats"; fail=1; }
[ "$rc_py"  -eq 0 ] || { echo "FAIL: test_queens.py exit=$rc_py"; fail=1; }

say "Layer 4: known non-termination (documented defect D1)"
# search(bd, 9, 0, 0) never terminates in ATS and blows the stack in Python.
# Run under a timeout so the suite itself cannot hang.
cat > out/hang.dats <<'HANG'
#define EIGHT_QUEENS_NO_MAIN 1
#include "./../eight_queens.dats"
implement main0 () =
  print! ("returned ", search ((0,0,0,0,0,0,0,0), 9, 0, 0), "\n")
HANG
$PATSCC $CF -o out/hang out/hang.dats 2>/dev/null || fail=1
rm -f hang_dats.c   # patscc emits the C file into the CWD, not beside -o
timeout 10 ./out/hang > /dev/null 2>&1
[ $? -eq 124 ] && echo "OK: ATS search(i=9) still non-terminating (as documented)" \
               || { echo "CHANGED: ATS search(i=9) now terminates"; fail=1; }

say "RESULT"
if [ "$fail" -eq 0 ]; then echo "ALL TESTS PASSED"; else echo "FAILURES"; fi
exit $fail
