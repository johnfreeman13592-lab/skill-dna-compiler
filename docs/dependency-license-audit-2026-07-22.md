# Dependency license audit — 2026-07-22

## Scope

This is a technical pre-publication audit, not legal advice. It checks package metadata for the
82 entries recorded in the Windows Beta build environment's `dependency-versions.txt`.

That inventory is deliberately conservative. It includes development and packaging tools such as
pytest and Ruff, so it must not be described as an exact list of files bundled in the ZIP.

## Result

- 82 package entries were resolved in the local build environment.
- 81 third-party entries exposed a license expression, license field, or license classifier.
- The only entry without installed license metadata was `skill-dna-compiler` itself; the project is
  covered by the repository's MPL-2.0 `LICENSE` and `pyproject.toml` declaration.
- PyInstaller metadata includes its GPL-2.0-or-later license and the special exception for bundled
  applications.
- No missing third-party package license metadata was found in this metadata-level pass.

The earlier packaged candidate contains 12 visible `.dist-info` directories. Eleven include their
license files. The Streamlit 1.59.2 wheel metadata declares Apache-2.0 but does not contain the
upstream `LICENSE` or `NOTICES` files. Version-pinned copies have therefore been added to the build
source, with fixed SHA-256 values checked before packaging. The upstream sources are:

- <https://github.com/streamlit/streamlit/blob/1.59.2/LICENSE>
- <https://github.com/streamlit/streamlit/blob/1.59.2/NOTICES>

## Remaining release check

Package metadata is not enough to prove which license and notice files are physically present in
the packaged application. Before publication:

1. Build the final ZIP from the exact public commit.
2. Map the PyInstaller contents to the dependency inventory.
3. Verify Streamlit 1.59.2's pinned `LICENSE` and `NOTICES` in the release bundle.
4. Confirm that every other required license or notice is included or reproduced as required.
5. Regenerate `dependency-versions.txt` and this audit if the lock set or build environment changes.
6. Treat any unclear or conflicting license as a release blocker until reviewed.

This remaining check does not require publishing the repository or contacting an external service.

## Automated candidate evidence

The `license-manifest-20260722` candidate completed this check at the build-environment level:

- dependency inventory: 82 packages
- collected installed license or notice files: 141
- explicit external entries: `skill-dna-compiler` and `streamlit`
- project MPL-2.0 license: included at ZIP root
- Streamlit 1.59.2 pinned `LICENSE` and `NOTICES`: included separately with fixed SHA-256 values
- manifest and dependency inventory: exact package-name match
- every manifest file: ZIP presence, byte size, and SHA-256 verified
- offline candidate verification: all 12 checks passed

Repeat the same automated collection and verification for the exact public commit. A dependency or
build-environment change invalidates this evidence and requires a new manifest.
