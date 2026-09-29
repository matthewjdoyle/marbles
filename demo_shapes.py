#!/usr/bin/env python3
"""Reproduce the wallpaper, tile, tessellation, and contact-sheet gallery."""

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from marble_tiling import tiled_preview
from marble_circles import MarbleGenerator
from marble_shapes import polygon_geometry, save_png, unused_path


EXAMPLES = [
    dict(name='phone_blue', title='Blue marble / phone', shape='rectangle',
         width=1080, height=1920, style='blue', seed=101),
    dict(name='desktop_golden', title='Golden marble / desktop', shape='rectangle',
         width=1920, height=1080, style='golden', seed=202),
    dict(name='desktop_jupiter', title='Jupiter / desktop', shape='rectangle',
         width=1920, height=1080, style='jupiter', seed=303),
    dict(name='triangle_burgundy', title='Burgundy / triangle', shape='triangle',
         width=512, height=512, style='burgundy', seed=404),
    dict(name='triangle_custom', title='Patina / custom triangle', shape='triangle',
         width=512, height=512, style='carrara', seed=505,
         colors=['#143C40', '#357C80', '#C79764', '#E9D7B5']),
    dict(name='hexagon_green', title='Serpentine / hexagon', shape='hexagon',
         width=512, height=512, style='green', seed=606),
    dict(name='hexagon_alien', title='Alien / hexagon', shape='hexagon',
         width=512, height=512, style='alien', seed=707),
]



def contact_sheet(entries):
    """Labeled overview; original images remain free of labels and framing."""
    width, margin, gap, card_width, card_height = 1500, 48, 24, 452, 400
    rows = math.ceil(len(entries) / 3)
    sheet = Image.new('RGB', (width, 170 + rows * (card_height + gap)), '#EEEAE2')
    draw = ImageDraw.Draw(sheet)
    title_font = ImageFont.load_default(size=38)
    label_font = ImageFont.load_default(size=22)
    meta_font = ImageFont.load_default(size=17)
    draw.text((margin, 35), 'MARBLE / SHAPES', fill='#242C2D', font=title_font)
    draw.text((margin, 91), 'Wallpapers, transparent tiles, and fitted layouts',
              fill='#59615F', font=label_font)
    for i, (title, image, subtitle) in enumerate(entries):
        x = margin + (i % 3) * (card_width + gap)
        y = 150 + (i // 3) * (card_height + gap)
        draw.rectangle((x, y, x + card_width, y + card_height), fill='#FAF8F3')
        preview = ImageOps.contain(image, (card_width - 32, 302), Image.Resampling.LANCZOS)
        px, py = x + (card_width - preview.width) // 2, y + 16 + (302 - preview.height) // 2
        sheet.paste(preview, (px, py), preview if preview.mode == 'RGBA' else None)
        draw.text((x + 16, y + 331), title, fill='#242C2D', font=label_font)
        draw.text((x + 16, y + 365), subtitle, fill='#59615F', font=meta_font)
    return sheet


def create_shape_gallery(output='shape_gallery'):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    entries, manifest, tiles = [], [], {}
    for example in EXAMPLES:
        generator = MarbleGenerator(width=example['width'], height=example['height'],
                                    seed=example['seed'])
        image = generator.generate_marble(example['shape'], example['style'],
                                          custom_colors=example.get('colors'))
        path = save_png(image, output / f"{example['name']}.png")
        record = {**example, 'file': path.name}
        if example['shape'] in ('triangle', 'hexagon'):
            record['geometry'] = polygon_geometry(example['shape'], *image.size)
            tiles.setdefault(example['shape'], []).append(image)
        manifest.append(record)
        entries.append((example['title'], image,
                        f"{image.width} x {image.height} px | seed {example['seed']}"))
        print(f'Saved {path}', flush=True)
    for shape in ('triangle', 'hexagon'):
        image = tiled_preview(shape, tiles[shape])
        path = save_png(image, output / f'{shape}_layout.png')
        manifest.append(dict(file=path.name, shape=shape, width=image.width,
                             height=image.height, tile_canvas=240,
                             geometry=polygon_geometry(shape, 240, 240)))
        entries.append((f'{shape.title()} / fitted layout', image,
                        'Alternating tiles | independent marble patterns'))
    sheet_path = save_png(contact_sheet(entries), output / 'contact_sheet.png')
    manifest_path = unused_path(output / 'manifest.json')
    manifest_path.write_text(json.dumps({'examples': manifest,
                                       'contact_sheet': sheet_path.name}, indent=2),
                             encoding='utf-8')
    print(f'Gallery: {sheet_path.resolve()}')
    return sheet_path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='shape_gallery')
    create_shape_gallery(parser.parse_args().output)
