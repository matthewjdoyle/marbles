#!/usr/bin/env python3
"""Generate the README's slanted marble gallery using the project renderer."""

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

from marble_circles import MarbleGenerator, MarbleStyle
from marble_shapes import unused_path


SIZE = (3072, 1024)
TEXTURE_SIZE = 1024
SLANT = 448
TOP_CUTS = (720, 1210, 1710, 2240, 2730)
PANELS = [
    dict(name='cyan', style='jupiter', seed=1207, rotation=90,
         colors=['#071622', '#083149', '#126784', '#42BED7', '#D3F5F4'],
         vein_scale=.012, texture_scale=.7, complexity=5, vein_intensity=.9),
    dict(name='patina', style='carrara', seed=505, rotation=0,
         colors=['#092E34', '#20636B', '#319294', '#CCA265', '#F0DEB8'],
         vein_scale=.009, texture_scale=.85, complexity=4, vein_intensity=.8),
    dict(name='amber', style='jupiter', seed=303, rotation=90,
         colors=['#48200C', '#9B450D', '#E89019', '#FFE0A1', '#FFF4D8'],
         vein_scale=.013, texture_scale=.7, complexity=5, vein_intensity=1.0),
    dict(name='violet', style='alien', seed=707, rotation=270,
         colors=['#241044', '#512294', '#9650DF', '#D49CFF', '#F4DFFF'],
         vein_scale=.012, texture_scale=.8, complexity=5, vein_intensity=.8),
    dict(name='coral', style='jupiter', seed=1909, rotation=90,
         colors=['#41172B', '#8D2B48', '#E6656E', '#FFB5A0', '#FFE4CD'],
         vein_scale=.010, texture_scale=.9, complexity=4, vein_intensity=.9),
    dict(name='charcoal', style='ice_world', seed=818, rotation=270,
         colors=['#101A22', '#35414A', '#738084', '#DAD8CB', '#FFF1D9'],
         vein_scale=.014, texture_scale=.75, complexity=5, vein_intensity=.8),
]


def compose_banner(textures):
    """Crop native textures into six antialiased, edge-to-edge diagonal panels."""
    if len(textures) != len(PANELS):
        raise ValueError(f'Expected {len(PANELS)} textures')
    width, height = SIZE
    top = (0, *TOP_CUTS, width)
    bottom = (0, *(cut - SLANT for cut in TOP_CUTS), width)
    banner = Image.new('RGB', SIZE, '#09121B')
    for index, texture in enumerate(textures):
        left = min(top[index], bottom[index])
        right = max(top[index + 1], bottom[index + 1])
        panel_size = (right - left, height)
        crop = ImageOps.fit(texture.convert('RGB'), panel_size,
                            method=Image.Resampling.LANCZOS)
        vertices = [(top[index] - left, 0), (top[index + 1] - left, 0),
                    (bottom[index + 1] - left, height),
                    (bottom[index] - left, height)]
        mask = Image.new('L', (panel_size[0] * 4, height * 4))
        ImageDraw.Draw(mask).polygon([(x * 4, y * 4) for x, y in vertices], fill=255)
        mask = mask.resize(panel_size, Image.Resampling.LANCZOS)
        banner.paste(crop, (left, 0), mask)
    # Separate the palettes with fine, consistently angled dark cuts.
    lines = Image.new('L', (width * 4, height * 4))
    draw = ImageDraw.Draw(lines)
    for cut in TOP_CUTS:
        draw.line((cut * 4, 0, (cut - SLANT) * 4, height * 4), fill=255, width=24)
    banner.paste('#09121B', (0, 0, width, height),
                 lines.resize(SIZE, Image.Resampling.LANCZOS))
    return banner


def create_banner(output='shape_gallery/gallery_banner.png', *, overwrite=False):
    destination = Path(output)
    if destination.suffix.lower() != '.png':
        raise ValueError('The banner output must have a .png extension')
    if not overwrite:
        destination = unused_path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    texture_dir = destination.parent / f'{destination.stem}_textures'
    texture_dir.mkdir(exist_ok=True)
    textures, records = [], []
    for panel in PANELS:
        print(f"Rendering {panel['name']} with MarbleGenerator...", flush=True)
        style = MarbleStyle(panel['name'], panel['colors'],
                            vein_intensity=panel['vein_intensity'],
                            vein_scale=panel['vein_scale'], complexity=panel['complexity'],
                            texture_scale=panel['texture_scale'])
        texture = MarbleGenerator(size=TEXTURE_SIZE, seed=panel['seed']).generate_marble(
            'rectangle', panel['style'], custom_style=style, deterministic_noise=True)
        texture_path = texture_dir / f"{panel['name']}.png"
        texture.save(texture_path, optimize=True)
        textures.append(texture.rotate(panel['rotation']))
        records.append({**panel, 'file': texture_path.relative_to(destination.parent).as_posix()})
    compose_banner(textures).save(destination, optimize=True)
    manifest = dict(renderer='marble_circles.MarbleGenerator', width=SIZE[0], height=SIZE[1],
                    texture_size=TEXTURE_SIZE, top_cuts=TOP_CUTS, slant=SLANT,
                    separator_width=6, panels=records)
    destination.with_suffix('.json').write_text(json.dumps(manifest, indent=2) + '\n',
                                                encoding='utf-8')
    print(f'Saved {destination.resolve()}', flush=True)
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='shape_gallery/gallery_banner.png')
    parser.add_argument('--overwrite', action='store_true',
                        help='Replace the selected banner and its generated textures')
    args = parser.parse_args()
    create_banner(args.output, overwrite=args.overwrite)
