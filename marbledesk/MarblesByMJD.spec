# Build from the repository root:
# python -m PyInstaller --noconfirm --distpath marbledesk/dist --workpath marbledesk/build marbledesk/MarblesByMJD.spec
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_dynamic_libs, copy_metadata

app_dir = Path(SPECPATH).resolve()
repo_dir = app_dir.parent

metadata = []
for package in ('PySide6', 'shiboken6', 'Pillow', 'numpy', 'noise'):
    metadata += copy_metadata(package)

a = Analysis(
    [str(app_dir / 'marble_studio.py')],
    pathex=[str(repo_dir)],
    binaries=collect_dynamic_libs('noise'),
    datas=metadata + [(str(app_dir / 'THIRD_PARTY_NOTICES.md'), '.'),
                      (str(app_dir / 'licenses'), 'licenses'),
                      (str(app_dir / 'assets/marbles-icon.png'), 'assets')],
    hiddenimports=['noise._perlin', 'noise._simplex'],
    excludes=['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets',
              'PySide6.QtQml', 'PySide6.QtQuick', 'tkinter', 'matplotlib'],
    noarchive=False,
)
# Modern Windows supplies the Universal CRT, ICU, and API-set forwarders. Collecting
# old copies from unrelated software on PATH can shadow the OS runtime and make
# Qt fail with "specified procedure could not be found" on an otherwise valid PC.
if sys.platform == 'win32':
    a.binaries = [entry for entry in a.binaries
                  if entry[0].lower() not in {'ucrtbase.dll', 'icuuc.dll', 'icuin.dll'}
                  and not entry[0].lower().startswith('api-ms-win-')
                  and not (entry[0].lower().startswith('icudt')
                           and not Path(entry[1]).is_relative_to(sys.prefix))]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='marbles by MJD',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False,
          icon=str(app_dir / 'assets/marbles-icon.ico') if sys.platform == 'win32' else None,
          version=str(app_dir / 'assets/windows-version.txt') if sys.platform == 'win32' else None,
          target_arch=None, codesign_identity=None, entitlements_file=None)
collection = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='marbles by MJD')
if sys.platform == 'darwin':
    app = BUNDLE(collection, name='marbles by MJD.app', icon=str(app_dir / 'assets/marbles-icon.icns'),
                 bundle_identifier='com.mjd.marbles',
                 info_plist={'NSHighResolutionCapable': True,
                             'CFBundleDisplayName': 'marbles by MJD',
                             'CFBundleName': 'marbles by MJD',
                             'CFBundleShortVersionString': '1.0.0',
                             'CFBundleVersion': '1',
                             'NSHumanReadableCopyright': 'See bundled third-party notices.'})
