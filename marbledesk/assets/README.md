# marbles by MJD icon

`marbles-icon-source.png` was generated with the built-in image tool. The prompt
requested one transparent, polished, classic marble-texture sphere using the
Earth preset colors: `#1E3A8A`, `#3B82F6`, `#10B981`, `#059669`, and `#F0F9FF`.
It explicitly excluded continents, maps, clouds, text, and a background.

Run `python marbledesk/assets/make_icons.py` from the repository root to build:

- `marbles-icon.png` and reduced PNG sizes for Qt and Linux
- `marbles-icon.ico` for the Windows executable
- `marbles-icon.icns` for the macOS app bundle

The source is raster artwork with detailed stone veining. The desktop builds
use raster icon formats; an SVG wrapper or favicon is not needed for this app.
