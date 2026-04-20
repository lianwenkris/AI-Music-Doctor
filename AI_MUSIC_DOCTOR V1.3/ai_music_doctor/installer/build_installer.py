#!/usr/bin/env python3
"""
AI Music Doctor - Windows Installer Builder
Creates Windows executable using PyInstaller

Version: 2.0.0
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
SRC_DIR = PROJECT_ROOT / 'src'
DIST_DIR = PROJECT_ROOT / 'dist'
BUILD_DIR = PROJECT_ROOT / 'build'
DOCS_DIR = PROJECT_ROOT / 'docs'
INSTALLER_DIR = PROJECT_ROOT / 'installer'

VERSION = '2.0.0'
APP_NAME = 'AI Music Doctor'
PUBLISHER = 'Denoise The Future Inc.'


def clean_build():
    """Remove previous build artifacts"""
    print("Cleaning previous builds...")
    for path in [DIST_DIR, BUILD_DIR]:
        if path.exists():
            shutil.rmtree(path)
            print(f"  Removed {path}")


def create_version_info():
    """Create version info file for Windows executable"""
    print("Creating version info...")
    
    version_info = f'''# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(2, 0, 0, 0),
    prodvers=(2, 0, 0, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          u'040904B0',
          [StringStruct(u'CompanyName', u'{PUBLISHER}'),
          StringStruct(u'FileDescription', u'{APP_NAME}'),
          StringStruct(u'FileVersion', u'{VERSION}'),
          StringStruct(u'InternalName', u'ai_music_doctor'),
          StringStruct(u'LegalCopyright', u'Copyright 2026 {PUBLISHER}'),
          StringStruct(u'OriginalFilename', u'AI_Music_Doctor.exe'),
          StringStruct(u'ProductName', u'{APP_NAME}'),
          StringStruct(u'ProductVersion', u'{VERSION}')])
      ]
    ),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
'''
    
    version_file = INSTALLER_DIR / 'version_info.txt'
    version_file.write_text(version_info)
    print(f"  Created {version_file}")
    return version_file


def generate_spec_file():
    """Generate PyInstaller spec file"""
    print("Generating PyInstaller spec file...")
    
    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-

import sys
sys.setrecursionlimit(5000)

a = Analysis(
    ['{SRC_DIR / "main.py"}'],
    pathex=['{SRC_DIR}'],
    binaries=[],
    datas=[
        ('{DOCS_DIR / "AI_Music_Doctor_Manual.pdf"}', '.'),
    ],
    hiddenimports=[
        'scipy.signal',
        'scipy.fft',
        'scipy.ndimage',
        'numpy.fft',
        'soundfile',
        'sounddevice',
        'pyqtgraph',
        'pyqtgraph.graphicsItems',
        'pyqtgraph.graphicsItems.PlotItem',
        'PyQt5.sip',
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib.backends.backend_tkagg'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='AI_Music_Doctor',
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
    version='{INSTALLER_DIR / "version_info.txt"}',
)
'''
    
    spec_file = PROJECT_ROOT / 'AI_Music_Doctor.spec'
    spec_file.write_text(spec_content)
    print(f"  Created {spec_file}")
    return spec_file


def generate_manual():
    """Generate PDF manual"""
    print("Generating PDF manual...")
    
    # Make sure docs directory exists
    DOCS_DIR.mkdir(exist_ok=True)
    
    # Run generate_manual.py
    manual_script = SRC_DIR / 'generate_manual.py'
    if manual_script.exists():
        result = subprocess.run(
            [sys.executable, str(manual_script)],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("  Manual generated successfully")
        else:
            print(f"  Warning: Manual generation failed: {result.stderr}")
    else:
        print(f"  Warning: Manual script not found at {manual_script}")


def run_pyinstaller():
    """Run PyInstaller to create executable"""
    print("Running PyInstaller...")
    
    spec_file = PROJECT_ROOT / 'AI_Music_Doctor.spec'
    
    result = subprocess.run(
        [sys.executable, '-m', 'PyInstaller', '--clean', str(spec_file)],
        capture_output=False
    )
    
    if result.returncode != 0:
        raise RuntimeError("PyInstaller failed")
    
    print("  Executable created successfully")


def copy_additional_files():
    """Copy additional files to dist directory"""
    print("Copying additional files...")
    
    # Create README for distribution
    readme_content = f'''AI Music Doctor v{VERSION}
===========================
{PUBLISHER}

THANK YOU for using AI Music Doctor!

=== WHAT'S NEW IN v2.0 ===

* TRUE REAL-TIME AUDIO MONITORING
  - Hear changes IMMEDIATELY as you adjust any knob
  - No need to process first - playback is processed live!
  
* AUTOMATIC AUDIO ANALYSIS
  - Loads file → Analyzes for issues → Suggests settings
  - Detects AI service (Suno, Udio, Tunee) automatically
  - Shows quality score and recommendations
  
* A/B COMPARISON
  - Toggle between Original (Dry) and Processed (Wet)
  - Compare in real-time during playback
  
* IMPROVED PRESETS
  - 17 presets including refined AI service presets
  - Problem-specific presets (De-Harsh, De-Ess, etc.)
  - Intensity presets (Light Touch to Maximum Restoration)
  
* SEEK & LOOP
  - Scrub through audio with seek slider
  - Loop playback for fine-tuning

=== QUICK START ===

1. Click "Load File" to open a WAV file
2. Review the automatic analysis results
3. Apply suggested settings or choose a preset
4. Press Play to hear processed audio in real-time
5. Adjust any knob - hear the change immediately!
6. Toggle A/B to compare Original vs Processed
7. Export when satisfied

=== SYSTEM REQUIREMENTS ===

- Windows 10/11 (64-bit)
- 4GB RAM minimum
- Audio output device

=== SUPPORT ===

For support, visit our documentation or contact:
support@denoisethefuture.com

Copyright (c) 2026 {PUBLISHER}
All rights reserved.
'''
    
    readme_file = DIST_DIR / 'README.txt'
    readme_file.write_text(readme_content)
    print(f"  Created {readme_file}")
    
    # Copy PDF manual if exists
    manual_pdf = DOCS_DIR / 'AI_Music_Doctor_Manual.pdf'
    if manual_pdf.exists():
        shutil.copy(manual_pdf, DIST_DIR)
        print(f"  Copied manual to dist")


def main():
    """Main build function"""
    print(f"\n{'='*50}")
    print(f"Building {APP_NAME} v{VERSION}")
    print(f"{'='*50}\n")
    
    try:
        clean_build()
        create_version_info()
        generate_manual()
        generate_spec_file()
        run_pyinstaller()
        copy_additional_files()
        
        print(f"\n{'='*50}")
        print("BUILD SUCCESSFUL!")
        print(f"Executable: {DIST_DIR / 'AI_Music_Doctor.exe'}")
        print(f"{'='*50}\n")
        
    except Exception as e:
        print(f"\nBUILD FAILED: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
