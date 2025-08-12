# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['ui.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('modules', 'modules'),        # Директория с модулями
        ('main.py', '.'),              # Главный скрипт
    ],
    hiddenimports=[
        'modules.config_manager',
        'modules.csv_processor',
        'modules.csv_reader',
        'modules.file_manager',
        'modules.logger_manager',
        'modules.xml_generator',
        'PyQt5',
        'PyQt5.QtWidgets',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
    ],
    hookspath=[],
    hooksconfig={},
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
    name='User_creator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)