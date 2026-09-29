"""Renderer adapter and spawned worker. No Qt imports in child processes."""
from pathlib import Path

from PIL import Image

from marble_circles import MarbleStyle
from .fast_renderer import FastMarbleGenerator
from marble_tiling import tiled_preview
from .model import Design, Composition
from .storage import save_image


def render_design(design):
    width, height = design.width, design.height
    style = MarbleStyle('Studio', list(design.colors), design.vein_intensity,
                        design.vein_scale, design.complexity, design.texture_scale)
    generator = FastMarbleGenerator(width=width, height=height, seed=design.seed)
    generator.studio_pattern = design.pattern
    generator.studio_seed = design.seed
    return generator.generate_marble(
        design.shape, design.planet_type if design.pattern == 'planetary' else 'carrara',
        intensity=design.intensity, custom_style=style, deterministic_noise=True,
        corner_radius=design.corner_radius, star_points=design.star_points,
        star_inner_ratio=design.star_inner_ratio)


def render_composition(composition, progress=lambda text: None):
    if not composition.tiles:
        raise ValueError('Add a triangle or hexagon design to the composition first')
    size = (composition.width, composition.height)
    tile_size = composition.tile_size
    images = []
    for index, recipe in enumerate(composition.tiles):
        progress(f'Rendering tile {index + 1} of {len(composition.tiles)}')
        # Render the saved recipe as-is: adding a nonsquare tile does not silently
        # replace its dimensions or alter its final texture.
        images.append(render_design(recipe))
    progress('Arranging tiles')
    return tiled_preview(composition.tiles[0].shape, images, size=size, tile_size=tile_size)


def worker(connection, request, directory):
    """Messages are small; full-resolution images travel through temporary files."""
    try:
        def progress(message):
            connection.send(('progress', message))
        progress('Rendering full-resolution image')
        if request['kind'] == 'tiling':
            image = render_composition(Composition.from_dict(request['recipe']), progress)
        else:
            image = render_design(Design.from_dict(request['recipe']))
        progress('Preparing final image')
        path = Path(directory) / 'render.png'
        # This is a temporary handoff, not the user's export. Avoid spending CPU
        # compressing an image that will immediately be decoded by the UI.
        image.save(path, compress_level=1)
        image.thumbnail((256, 256))
        thumbnail = Path(directory) / 'thumbnail.png'
        image.save(thumbnail)
        connection.send(('result', {'path': str(path), 'thumbnail': str(thumbnail)}))
    except BaseException as error:
        connection.send(('error', f'{type(error).__name__}: {error}'))
    finally:
        connection.close()


def export_worker(connection, source, target):
    """A short, separate commit phase is allowed to finish during cancellation."""
    try:
        with Image.open(source) as image:
            result = save_image(target, image)
        connection.send(('result', str(result)))
    except BaseException as error:
        connection.send(('error', f'{type(error).__name__}: {error}'))
    finally:
        connection.close()
