@echo off
echo [1/3] Skeniruem kod cherez AST...
call graphify . --code-only

echo [2/3] Generiruem GRAPH_REPORT.md...
call graphify cluster-only .

echo [3/3] Kopiruem otchet v Obsidian...
if not exist "vault\graphify" mkdir "vault\graphify"
xcopy /Y "graphify-out\GRAPH_REPORT.md" "vault\graphify\"

echo [DONE] Karta proekta uspeshno obnovlena v Obsidian!
pause
