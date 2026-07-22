# Contributing

Thank you for helping improve Skill DNA Compiler.

During the first public Beta, please start with a GitHub Discussion for questions and feature
ideas, and use the bug-report Issue Form for reproducible defects. Before opening a pull request,
discuss the intended change with the maintainer so that safety boundaries and the narrow Beta scope
remain consistent.

## Development checks

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,package]"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
```

Never commit API keys, `.env.local`, databases, backups, generated Skills, private notes, build
artifacts, or personal filesystem paths. Tests must use synthetic fixtures.

Contributions to files covered by this repository are accepted under the Mozilla Public License
2.0. See `LICENSE`.
