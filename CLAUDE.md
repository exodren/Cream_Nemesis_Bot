# Claude Code Memory & Optimization Rules
- Before processing any task, ALWAYS read `./graphify-out/GRAPH_REPORT.md` to understand the codebase layout. DO NOT rescan the directories manually.
- Apply `Ponytail` rules: provide brief, condensed code snippets. Avoid redundant formatting, massive comments, or boilerplate code.
- Always communicate and respond in Russian language.

# Project Architecture Summary (Game Bot)
- Entry point: main() with DbSessionMiddleware and 8-hour log rotation.
- Tech Stack: aiogram 3 (FSM), SQLAlchemy async + SQLite, APScheduler, Pillow (PIL image rendering).
- Key Entities: User, Match, Goal, Season, SeasonParticipant, Warning, LplRosterMember.
- Critical Nodes: edit_screen(), get_settings(), back_kb().
