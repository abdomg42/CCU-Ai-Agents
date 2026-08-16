#!/usr/bin/env bash
# Build script for rapport/main.tex
# Workaround: MiKTeX fails if the PATH contains entries that point to a file
# (e.g. C:\...\python.exe) instead of a directory. We filter those out.
set -e

cd "$(dirname "$0")"

# Remove any PATH entries ending in .exe so MiKTeX treats them as directories.
export PATH=$(echo "$PATH" | tr ':' '\n' | grep -v '\.exe$' | tr '\n' ':')

echo "Running pdflatex (1/3)..."
pdflatex -interaction=nonstopmode main.tex

echo "Running bibtex..."
bibtex main

echo "Running pdflatex (2/3)..."
pdflatex -interaction=nonstopmode main.tex

echo "Running pdflatex (3/3)..."
pdflatex -interaction=nonstopmode main.tex

echo "Build complete: main.pdf"
