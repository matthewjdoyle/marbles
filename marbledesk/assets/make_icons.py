"""Build desktop icon formats from the generated transparent marble master."""
from pathlib import Path

from PIL import Image, ImageFilter


HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'marbles-icon-source.png'


def main():
    source = Image.open(SOURCE).convert('RGBA')
    alpha = source.getchannel('A')
    # Generated artwork has nearly transparent stray pixels beyond the sphere.
    alpha = alpha.point(lambda value: value if value >= 16 else 0)
    source.putalpha(alpha)
    bounds = alpha.getbbox()
    if not bounds:
        raise ValueError('The generated marble has no visible pixels')
    sphere = source.crop(bounds)
    diameter = 920
    sphere.thumbnail((diameter, diameter), Image.Resampling.LANCZOS)
    master = Image.new('RGBA', (1024, 1024), (0, 0, 0, 0))
    master.alpha_composite(sphere, ((1024 - sphere.width) // 2, (1024 - sphere.height) // 2))
    master.save(HERE / 'marbles-icon.png', optimize=True)

    for size in (512, 256, 128, 64, 32, 16):
        icon = master.resize((size, size), Image.Resampling.LANCZOS)
        if size <= 32:
            icon = icon.filter(ImageFilter.UnsharpMask(radius=.6, percent=125, threshold=2))
        icon.save(HERE / f'marbles-icon-{size}.png', optimize=True)

    master.save(HERE / 'marbles-icon.ico', format='ICO',
                sizes=[(size, size) for size in (16, 32, 48, 64, 128, 256)],
                bitmap_format='png')
    master.save(HERE / 'marbles-icon.icns', format='ICNS')


if __name__ == '__main__':
    main()
