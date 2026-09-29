# marbles by MJD validation

Verified locally on Windows 11 x64, 24 September 2026.

## Results

- All **40 core tests passed**, including version 1 and 2 migration, shape, selector, wheel,
  palette-button, and 8K composition checks.
- Source GUI workflow smoke test passed.
- Rebuilt Windows executable workflow smoke test passed with Qt's offscreen and
  native Windows backends. Source smoke also passed at 200% scaling.
- New portable archive: `marbledesk/dist/marbles-by-MJD-windows-x64.zip`.
- New launcher: `marbledesk/dist/marbles by MJD/marbles by MJD.exe`.
- Windows file description and product name are `marbles by MJD`; the executable
  has the generated Earth-palette marble icon. PNG and ICNS assets are prepared
  for Linux and macOS builds.
- Superseded release folders and the temporary PyInstaller `build` directory were removed.

The workflow test covers editing, undo/redo, seed locking, exact render/export
pixel matching, numbered exports, stale-result rejection, batch manifests,
importing batch recipes from a manifest, ordered tiling, document save/open, cancellation,
preservation of completed batch files, and recovery after worker errors.

## Exact-only rendering update

Approximate drafts have been removed. Automatic canvas renders use the exact
export dimensions and populate the same final-image cache used for PNG export.
Changes cancel obsolete automatic renders, and Export reuses a matching render
already in progress. The GUI smoke test exercises these paths.

The accelerated NumPy sampler matches the original noise C extension on random
coordinates, negative coordinates, repeat boundaries, and multiple octave settings.
Pixel comparisons pass for all 15 styles on all four shapes, plus custom texture
parameters and multiple processing blocks. No GPU or new dependency is required.

Local 1024 × 1024 measurements (median of three runs, same seed, identical pixels):

| Style | Reference CPU | Accelerated CPU | Speedup |
| --- | --- | --- | --- |
| Carrara | 6.756 s | 0.953 s | 7.09× |
| Jupiter | 11.459 s | 1.412 s | 8.11× |

Times measure rendering, excluding worker startup, file handoff, and UI display.
Reproduce with `python -m marbledesk.benchmark_studio --size 1024 --runs 3`.

The new 7680 × 4320 hexagon composition rendered in 0.35 seconds on this
Windows machine using a 2048-pixel tile canvas and a saved 64 × 64 tile recipe.
The image had exact dimensions and no black gaps. The compositor uses native
resolution for large canvases to avoid a 2x intermediate image.
The standalone 7680 × 4320 rectangle rendered in 20.56 seconds. Studio color
assembly now uses row blocks to avoid several full-size NumPy arrays.

## Runtime and packaging

Local verification used Python 3.13.1, PySide6 6.11.2, PyInstaller 6.22.3,
NumPy 2.5.3, Pillow 12.3.0, and noise 1.2.2.

The build configuration excludes Windows system CRT/API-set/ICU libraries that
can otherwise be picked up from unrelated programs on PATH and shadow the OS
versions. The final packaged executable was tested after this fix.

The Windows ZIP contains the complete portable folder. Extract it and keep the
`_internal` directory next to the executable. No separate Python installation
is needed.

## Platform limits

macOS Intel, macOS Apple Silicon, and Linux x64 build-and-test jobs are configured
in `.github/workflows/desktop.yml`. Those jobs were **not run locally**; this
workspace is on Windows. No signed or notarized release was produced.

The current packaged smoke results are under `marbledesk/.verification/branded-final-offscreen/`
and `marbledesk/.verification/branded-final-native/`. New source screenshots are under
`marbledesk/.verification/renamed-source/`. The earlier 200% scaling result is under
`marbledesk/.verification/final-hidpi/`.
