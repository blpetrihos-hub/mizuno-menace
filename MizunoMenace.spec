# PyInstaller spec for Mizuno Menace - builds a single self-contained exe.
# Build with:  pyinstaller MizunoMenace.spec   (or use build.ps1)

block_cipher = None

a = Analysis(
    ["run.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("mizuno_menace/assets", "mizuno_menace/assets"),
        ("mizuno_menace/data", "mizuno_menace/data"),
    ],
    hiddenimports=[
        "mizuno_menace.deal_scorer",
        "mizuno_menace.reference_resolver",
        "mizuno_menace.sources.ebay_source",
        "mizuno_menace.sources.footstore_source",
        "mizuno_menace.sources.demo_source",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="MizunoMenace",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
