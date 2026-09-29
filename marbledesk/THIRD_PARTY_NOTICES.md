# Third-party components

Marble Studio uses Python, PySide6/Qt, Shiboken, Pillow, NumPy, and noise.
Standalone packages include dependency metadata and the licenses supplied by
their distributions. Qt and PySide6 are dynamically linked; their libraries are
kept as separate files in the portable distribution.

- Python: Python Software Foundation License — https://www.python.org/psf/license/
- PySide6, Shiboken and Qt: LGPL/GPL/commercial terms as applicable to each
  bundled component — https://doc.qt.io/qtforpython-6/licenses.html
- Pillow: HPND — https://github.com/python-pillow/Pillow
- NumPy: BSD-3-Clause, plus bundled dependency notices — https://numpy.org/doc/stable/license.html
- noise: MIT — https://github.com/caseman/noise
- PyInstaller bootloader: GPL with the bundling exception — https://pyinstaller.org/en/stable/license.html

Before redistributing a modified build, retain the licenses and notices supplied
with each dependency, and review the applicable Qt redistribution terms.

The vectorized sampler in `marbledesk/studio/noise_vector.py` adapts the 2D Perlin algorithm
and lookup tables from Casey Duncan's noise library. Its MIT copyright and
license are included in `marbledesk/licenses/noise-MIT.txt`.
