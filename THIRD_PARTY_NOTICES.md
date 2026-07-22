# Third-party notices

Skill DNA Compiler Beta is built with third-party Python packages and may bundle them in the
portable Windows distribution. Direct runtime and packaging dependencies are listed below.
The adjacent `dependency-versions.txt` is a conservative inventory of the build environment; it
also contains development tools and is not proof that every listed package is present in the ZIP.

| Package | License |
| --- | --- |
| keyring | MIT |
| openai | Apache-2.0 |
| platformdirs | MIT |
| pydantic | MIT |
| pydantic-settings | MIT |
| python-frontmatter | MIT |
| PyYAML | MIT |
| SQLAlchemy | MIT |
| Streamlit | Apache-2.0 |
| PyInstaller | GPL-2.0-or-later with a special exception for bundled applications |

Transitive dependencies remain subject to their respective licenses. This file is not a
replacement for the license metadata and notices shipped by each dependency. Before publication,
complete the bundled-file-level review described in the dependency-license audit. The portable
distribution includes Streamlit 1.59.2's pinned upstream `LICENSE` and `NOTICES` under
`THIRD_PARTY_LICENSES/streamlit-1.59.2/`.
