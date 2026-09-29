"""Shared gap-free polygon composition for the CLI and desktop studio."""
import math
from PIL import Image, ImageDraw, ImageOps
from marble_shapes import polygon_geometry


def tiled_preview(shape, tiles, size=(1200, 800), tile_size=240):
    """Tessellate tiles using polygon vertices, not their transparent PNG bounds.

    Rasterize touching polygons on one 2x canvas and downsample once. This avoids
    alpha seams from layering independently antialiased tile edges. Texture
    colors are opaque beneath the masks; they are not required to match edges.
    """
    width, height = size
    # A 2x 8K RGB canvas alone exceeds 1.2 GiB. At large sizes the native
    # resolution already provides enough coverage for a one-pixel edge.
    scale = 1 if width * height > 8_000_000 else 2
    canvas = Image.new('RGB', (width * scale, height * scale))
    geometry = polygon_geometry(shape, tile_size, tile_size)
    left, top, right, bottom = geometry['bounds']
    side = geometry['side']
    tile_height = bottom - top
    tile_width = right - left
    texture_pixels = round(tile_size * scale)
    textures = [tile.convert('RGB').resize((texture_pixels, texture_pixels),
                                          Image.Resampling.LANCZOS) for tile in tiles]
    if not textures:
        raise ValueError('At least one tile image is required')

    def stamp(x, y, index, flipped=False):
        vertices = geometry['vertices']
        if flipped:
            vertices = [(tile_size - vx, tile_size - vy) for vx, vy in vertices]
        # x/y are the geometric bounding-box origin, not the image origin.
        origin_x, origin_y = x - left, y - top
        px, py = round(origin_x * scale), round(origin_y * scale)
        texture = textures[index % len(textures)]
        if flipped:
            texture = texture.transpose(Image.Transpose.ROTATE_180)
        # A one-pixel border includes rasterized shared endpoints at W or H.
        # Extend RGB only; the actual polygon mask controls the visible extent.
        texture = ImageOps.expand(texture, border=1)
        texture.paste(texture.crop((1, 1, 2, texture.height - 1)), (0, 1))
        texture.paste(texture.crop((texture.width - 2, 1, texture.width - 1,
                                   texture.height - 1)), (texture.width - 1, 1))
        texture.paste(texture.crop((0, 1, texture.width, 2)), (0, 0))
        texture.paste(texture.crop((0, texture.height - 2, texture.width,
                                   texture.height - 1)), (0, texture.height - 1))
        mask = Image.new('L', texture.size)
        points = [(round((vx + origin_x) * scale) - px + 1,
                   round((vy + origin_y) * scale) - py + 1) for vx, vy in vertices]
        ImageDraw.Draw(mask).polygon(points, fill=255)
        canvas.paste(texture, (px - 1, py - 1), mask)

    if shape == 'triangle':
        for row in range(-1, math.ceil(height / tile_height) + 1):
            for col in range(-2, math.ceil(width / (side / 2)) + 2):
                stamp(col * side / 2, row * tile_height,
                      row + col, flipped=bool((row + col) % 2))
    else:
        for col in range(-1, math.ceil(width / (1.5 * side)) + 1):
            for row in range(-1, math.ceil(height / tile_height) + 1):
                stamp(col * 1.5 * side, (row + (col % 2) / 2) * tile_height,
                      row + col)
    return canvas if scale == 1 else canvas.resize(size, Image.Resampling.LANCZOS)

