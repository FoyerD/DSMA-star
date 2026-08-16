#!/usr/bin/env bash
# Build the paper (4-pass pdflatex + bibtex) and verify it is clean:
#   - compiles with -halt-on-error (any LaTeX error aborts)
#   - no undefined references/citations in the final pass
#   - no overfull hboxes
# Prints the final table numbering from main.aux.
#
# Run from anywhere: it locates the LaTeX project (gitignored `ignore/`)
# relative to this script. On failure, the tail of the pdflatex transcript is
# dumped to stderr.
set -euo pipefail

PAPER_DIR="$(cd "$(dirname "$0")/../ignore" && pwd)"
cd "$PAPER_DIR"

[ -f main.tex ] || { echo "error: main.tex not found in $PAPER_DIR" >&2; exit 1; }

run_pdflatex() {
    pdflatex -interaction=nonstopmode -halt-on-error main.tex >"$1" 2>&1
}

echo "pdflatex pass 1/4..."
if ! run_pdflatex /tmp/opencode/tex_pass1.log; then
    tail -40 /tmp/opencode/tex_pass1.log >&2; exit 1
fi
echo "bibtex..."
if ! bibtex main >/tmp/opencode/tex_bibtex.log 2>&1; then
    cat /tmp/opencode/tex_bibtex.log >&2; exit 1
fi
for n in 2 3 4; do
    echo "pdflatex pass $n/4..."
    if ! run_pdflatex /tmp/opencode/tex_pass$n.log; then
        tail -40 /tmp/opencode/tex_pass$n.log >&2; exit 1
    fi
done

echo "BUILD OK"

if rg -n "undefined" main.log; then
    echo "FAIL: undefined references/citations (see main.log)" >&2
    exit 1
fi

if rg -n "Overfull" main.log; then
    echo "FAIL: overfull hbox (see main.log)" >&2
    exit 1
fi

echo
echo "Table numbering (from main.aux):"
rg "newlabel\{tab:" main.aux | sed 's/^[0-9]*://'
