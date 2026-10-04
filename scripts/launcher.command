#!/bin/zsh
# Lanceur macOS : double-clic (ou icône du Dock) → ouvre Terminal et traite les TCX de ~/Downloads.
cd "${0:A:h}/.." || exit 1
python3 scripts/process_tcx_files.py
echo
read -k 1 "?Appuie sur une touche pour fermer…"
