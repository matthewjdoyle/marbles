# marbles by MJD desktop app

`marbledesk` contains the offline desktop editor for the marble artwork in the
[main project](../README.md). It uses the shared generators in the repository
root and adds an interactive interface, a faster final renderer, batch creation,
and tile composition. The interface follows the system light or dark theme.

## Run from source

Use Python 3.10 or newer. Run these commands from the repository root:

```powershell
# Windows
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r marbledesk/requirements-gui.txt
.venv\Scripts\python.exe -m marbledesk.marble_studio
```

```bash
# macOS / Linux
python3 -m venv .venv
.venv/bin/python -m pip install -r marbledesk/requirements-gui.txt
.venv/bin/python -m marbledesk.marble_studio
```

Installing `noise` may require a C compiler if no wheel is available. The CLI
generators need only the root `requirements.txt` and do not require Qt.

## Make a design

1. In **Studio**, choose a pattern, palette, and shape. Edit, reorder, or reset
   palette colors independently of the pattern. **Planetary** reveals a separate
   planet type control.
2. Set canvas dimensions and tune intensity, vein strength, vein frequency,
   complexity, texture frequency, and seed. The seed lock keeps variations
   reproducible.
3. The canvas renders at the chosen export dimensions. Use **Fit**, **100%**,
   zoom buttons, or Control + mouse wheel to inspect it; drag to pan.
4. Choose **Export PNG…**. Export uses the inspected final render when it is
   current. An existing filename gets a numbered alternative.

**Save** writes a versioned JSON document with design, batch settings, tile
recipes, and renderer version. **Open…**, Undo, and Redo are supported. The app
checks unsaved changes before opening another document or closing. Version 1 and
2 documents migrate when opened.

| Control | Range |
| --- | --- |
| Intensity | 0.1–2.0 |
| Vein strength | 0.3–1.2 |
| Vein frequency | 0.010–0.030 |
| Complexity | 2–5 noise layers |
| Texture frequency | 0.5–2.0 |
| Seed | 0–2,147,483,647 |
| Canvas dimensions | 64–8192 pixels; circles require a square canvas |

## Batch and tiling

**Batch** starts from the Studio design and changes seeds. It can also vary
palettes, texture parameters, and output sizes. A completed batch includes a
manifest with recipes, output paths, and completion status. Cancellation keeps
completed images. A manifest recipe can be reconstructed with
`marbledesk.studio.model.Design.from_dict`.

**Tiling** places generated triangles or hexagons on a wallpaper canvas. Add the
current Studio design or recipes from a saved batch, order the tiles, then set
wallpaper and tile dimensions. Geometric placement avoids gaps, though adjacent
marble veins need not meet continuously. Tiling export uses the same final-render
workflow as Studio.

Heavy rendering runs in a separate process, one job at a time. Worker failures
leave the editor available. Large canvases can take substantial time and memory.
PNG publication uses hard links for atomic, non-overwriting saves, so use a local
filesystem with hard-link support.

## Rendering and verification

`studio/fast_renderer.py` evaluates the shared Perlin noise equations in NumPy
row blocks. It uses the same pixel values as the reference renderer and needs no
GPU or additional dependencies. The original CLI renderer stays in the repository
root. To compare render times and confirm pixel equality:

```bash
python -m marbledesk.benchmark_studio --size 1024 --runs 3
```

Run the regression and GUI smoke checks from the repository root:

```bash
python -m unittest discover -s tests -q
python -m unittest discover -s marbledesk/tests -q
python -m marbledesk.marble_studio --smoke-test
```

For headless runs, set `QT_QPA_PLATFORM=offscreen`. Set
`MARBLE_SMOKE_OUTPUT=marbledesk/.verification/studio` to collect screenshots;
`QT_SCALE_FACTOR=2` exercises high-DPI scaling. The smoke check covers editing,
history, seed locking, exact export, filename collisions, batch and tiling jobs,
save/open, cancellation, and recovery. See [desktop validation](DESKTOP_VALIDATION.md)
for earlier local results.

Saved designs use renderer version `deterministic-1`. The app enables stable noise
sampling for all shapes; the shared generator keeps its original circle behavior
by default for existing callers. Unknown renderer versions are rejected rather
than silently reinterpreted.

## Build a portable app

Build on each target operating system, from the repository root:

```bash
python -m pip install -r marbledesk/requirements-build.txt
python -m PyInstaller --noconfirm --distpath marbledesk/dist --workpath marbledesk/build marbledesk/MarblesByMJD.spec
```

The complete Windows or Linux package is `marbledesk/dist/marbles by MJD/`;
keep `_internal` beside the executable. On macOS, the output is
`marbledesk/dist/marbles by MJD.app`. These packages do not require a separate
Python installation. Regenerate the app icons with
`python marbledesk/assets/make_icons.py`; see [assets](assets/README.md) and
[third-party notices](THIRD_PARTY_NOTICES.md).

The [desktop CI workflow](../.github/workflows/desktop.yml) builds Windows x64,
Linux x64, macOS Intel, and macOS Apple Silicon artifacts, runs source and
package checks, and uploads screenshots. Linux packages need a compatible glibc,
graphical desktop, and Qt system libraries. Packages are unsigned; release
signing and macOS notarization need credentials.

## Folder map

| Path | Purpose |
| --- | --- |
| `marble_studio.py` | App entry point and packaged smoke-test switch |
| `studio/` | UI, document model, job management, storage, rendering, and smoke checks |
| `tests/` | Desktop behavior and pixel equivalence tests |
| `assets/`, `licenses/` | App icons and bundled license text |
| `MarblesByMJD.spec` | Portable build configuration |
| `requirements-gui.txt`, `requirements-build.txt` | App and packaging dependencies |
| `benchmark_studio.py` | Reference versus accelerated renderer comparison |
