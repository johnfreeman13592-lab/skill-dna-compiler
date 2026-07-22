from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata


project_root = Path(SPECPATH).resolve().parent
hidden_imports = collect_submodules("keyring.backends")
# app.py is loaded by Streamlit at runtime, so PyInstaller cannot discover its imports
# through the launcher entry point. Collect both runtime module trees explicitly.
hidden_imports += collect_submodules("streamlit")
hidden_imports += collect_submodules("skill_dna_compiler")
data_files = [(str(project_root / "app.py"), ".")]
data_files += copy_metadata("streamlit")
data_files += collect_data_files("streamlit", excludes=[".agents"])

a = Analysis(
    [str(project_root / "src" / "skill_dna_compiler" / "launcher.py")],
    pathex=[str(project_root), str(project_root / "src")],
    binaries=[],
    datas=data_files,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "ruff"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Skill DNA Compiler",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Skill DNA Compiler",
)
