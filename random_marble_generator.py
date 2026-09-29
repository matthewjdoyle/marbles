#!/usr/bin/env python3
"""
Random Marble Generator

Generates marble circles with randomly generated parameters including:
- Color palettes
- Vein intensity
- Vein scale
- Complexity levels

Perfect for creating diverse marble texture collections and exploring
parameter combinations automatically.
"""

import argparse
import random
import colorsys
import math
from pathlib import Path
from typing import List, Tuple, Optional
import sys
from datetime import datetime

from marble_circles import MarbleGenerator, MarbleStyle
from marble_shapes import SHAPES, save_png, unused_path


class RandomMarbleGenerator:
    """Generates marble textures with random parameters."""
    
    def __init__(self, seed: int = None):
        """Initialize random marble generator.
        
        Args:
            seed: Random seed for reproducible results
        """
        if seed is not None:
            random.seed(seed)
    
    def generate_random_colors(self, count: int = None, scheme: str = 'random') -> List[str]:
        """Generate a harmonious random color palette.
        
        Args:
            count: Number of colors (3-6 if None)
            scheme: Color scheme type ('random', 'analogous', 'complementary', 'triadic', 'monochromatic')
            
        Returns:
            List of hex color strings
        """
        if count is None:
            count = random.randint(3, 6)
        
        # Base hue for color schemes
        base_hue = random.random()
        base_saturation = random.uniform(0.4, 0.9)
        
        colors = []
        
        if scheme == 'analogous':
            # Colors close to each other on color wheel
            for i in range(count):
                hue = (base_hue + (i * 0.08)) % 1.0  # Small hue variations
                saturation = base_saturation + random.uniform(-0.2, 0.2)
                saturation = max(0.2, min(0.9, saturation))
                value = random.uniform(0.4, 0.9)
                colors.append(self._hsv_to_hex(hue, saturation, value))
                
        elif scheme == 'complementary':
            # Base color and its complement plus variations
            for i in range(count):
                if i < count // 2:
                    hue = (base_hue + random.uniform(-0.05, 0.05)) % 1.0
                else:
                    hue = (base_hue + 0.5 + random.uniform(-0.05, 0.05)) % 1.0
                saturation = base_saturation + random.uniform(-0.2, 0.2)
                saturation = max(0.2, min(0.9, saturation))
                value = random.uniform(0.3, 0.9)
                colors.append(self._hsv_to_hex(hue, saturation, value))
                
        elif scheme == 'triadic':
            # Three colors equally spaced on color wheel
            hue_offsets = [0, 0.33, 0.67]
            for i in range(count):
                base_offset = hue_offsets[i % 3]
                hue = (base_hue + base_offset + random.uniform(-0.03, 0.03)) % 1.0
                saturation = base_saturation + random.uniform(-0.15, 0.15)
                saturation = max(0.3, min(0.9, saturation))
                value = random.uniform(0.4, 0.9)
                colors.append(self._hsv_to_hex(hue, saturation, value))
                
        elif scheme == 'monochromatic':
            # Same hue, different saturation and value
            for i in range(count):
                hue = base_hue + random.uniform(-0.02, 0.02)
                saturation = random.uniform(0.3, 0.9)
                value = random.uniform(0.3, 0.9)
                colors.append(self._hsv_to_hex(hue, saturation, value))
                
        else:  # 'random'
            # Completely random colors with some constraints for harmony
            for i in range(count):
                hue = random.random()
                saturation = random.uniform(0.4, 0.9)
                value = random.uniform(0.3, 0.9)
                colors.append(self._hsv_to_hex(hue, saturation, value))
        
        return colors
    
    def _hsv_to_hex(self, h: float, s: float, v: float) -> str:
        """Convert HSV to hex color string."""
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
    
    def generate_random_parameters(self) -> dict:
        """Generate random marble parameters.
        
        Returns:
            Dictionary with random parameters
        """
        return {
            'vein_intensity': random.uniform(0.3, 1.2),
            'vein_scale': random.uniform(0.010, 0.030),
            'complexity': random.randint(2, 5),
            'texture_scale': random.uniform(0.5, 2.0)  # Controls overall texture element size
        }
    
    def create_random_marble_style(self, name: str = None, color_scheme: str = 'random') -> MarbleStyle:
        """Create a completely random marble style.
        
        Args:
            name: Style name (auto-generated if None)
            color_scheme: Color scheme type
            
        Returns:
            MarbleStyle with random parameters
        """
        if name is None:
            name = f"Random_{random.randint(1000, 9999)}"
        
        colors = self.generate_random_colors(scheme=color_scheme)
        params = self.generate_random_parameters()
        
        return MarbleStyle(
            name=name,
            colors=colors,
            vein_intensity=params['vein_intensity'],
            vein_scale=params['vein_scale'],
            complexity=params['complexity'],
            texture_scale=params['texture_scale']
        )
    
    def generate_marble_batch(self, output_dir: str, batch_size: int = 10, 
                             sizes: List[int] = None, color_schemes: List[str] = None,
                             intensity_range: Tuple[float, float] = (0.8, 1.2), *,
                             shape: str = 'circle', width: Optional[int] = None,
                             height: Optional[int] = None) -> None:
        """Generate a batch of random marble images.
        
        Args:
            output_dir: Output directory path
            batch_size: Number of marbles to generate per size
            sizes: List of image sizes (default: [512, 1024])
            color_schemes: List of color schemes to use
            intensity_range: Range for intensity variation
        """
        canvases = self._canvases(sizes, width, height, shape)
        if not isinstance(batch_size, int) or batch_size < 1:
            raise ValueError('batch_size must be a positive integer')
        if not all(math.isfinite(v) for v in intensity_range) or not (
                0.1 <= intensity_range[0] < intensity_range[1] <= 2.0):
            raise ValueError('Intensity range must satisfy 0.1 <= min < max <= 2.0')
        sizes = [f'{w}x{h}' for w, h in canvases]
        
        if color_schemes is None:
            color_schemes = ['random', 'analogous', 'complementary', 'triadic', 'monochromatic']
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        print(f"Generating Random Marble Batch")
        print("=" * 50)
        print(f"Output: {output_path.absolute()}")
        print(f"Batch size: {batch_size} marbles per size")
        print(f"Sizes: {sizes}")
        print(f"Color schemes: {color_schemes}")
        if output_path.exists() and any(output_path.iterdir()):
            existing_files = len([f for f in output_path.iterdir() if f.suffix.lower() == '.png'])
            print(f"Appending to existing collection ({existing_files} existing images)")
        print()
        
        total_generated = 0
        total_size_mb = 0
        
        for canvas_width, canvas_height in canvases:
            size = canvas_width
            print(f"Generating {canvas_width}x{canvas_height} {shape} marbles...")
            
            for i in range(batch_size):
                # Choose random color scheme
                color_scheme = random.choice(color_schemes)
                
                # Create random marble style
                style_name = f"random_{color_scheme}_{size}px_{i+1:03d}"
                if shape != 'circle':
                    style_name = f'random_{color_scheme}_{shape}_{canvas_width}x{canvas_height}_{i+1:03d}' 
                marble_style = self.create_random_marble_style(style_name, color_scheme)
                
                # Random intensity within range
                intensity = random.uniform(*intensity_range)
                
                # Generate unique seed for this marble
                marble_seed = random.randint(1, 1000000)
                
                # Create timestamp for unique filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # Include milliseconds
                
                # Create generator and generate marble
                generator = MarbleGenerator(width=canvas_width, height=canvas_height, seed=marble_seed)
                
                # Create custom marble using the random style
                # Keep the legacy circle batch palette behavior. New shapes
                # also use the generated vein scale, complexity and texture scale.
                render_options = ({'custom_colors': [f'#{r:02x}{g:02x}{b:02x}'
                                   for r, g, b in marble_style.colors]}
                                  if shape == 'circle' else {'custom_style': marble_style})
                image = generator.generate_marble(shape=shape, intensity=intensity,
                                                  **render_options)
                
                # Save with descriptive filename including timestamp for uniqueness
                filename = f"{style_name}_{timestamp}_i{intensity:.2f}_s{marble_seed}.png"
                filepath = output_path / filename
                
                # Ensure no filename conflicts (extra safety)
                counter = 1
                while filepath.exists():
                    filename = f"{style_name}_{timestamp}_{counter:02d}_i{intensity:.2f}_s{marble_seed}.png"
                    filepath = output_path / filename
                    counter += 1
                
                filepath = save_png(image, filepath)
                file_size = filepath.stat().st_size / 1024 / 1024  # MB
                total_size_mb += file_size
                total_generated += 1
                
                print(f"  [{i+1:2d}/{batch_size}] {filename} ({file_size:.2f} MB)")
                print(f"      Scheme: {color_scheme} | Intensity: {intensity:.2f} | Complexity: {marble_style.complexity}")
                print(f"      Colors: {len(marble_style.colors)} | Vein Scale: {marble_style.vein_scale:.3f} | Texture Scale: {marble_style.texture_scale:.2f}")
        
        print("\n" + "=" * 50)
        print(f"Random Marble Batch Complete!")
        print(f"Total Generated: {total_generated} images")
        print(f"Total Size: {total_size_mb:.1f} MB")
        
        # Show total collection size including existing images
        if output_path.exists():
            all_images = len([f for f in output_path.iterdir() if f.suffix.lower() == '.png'])
            print(f"Total Collection: {all_images} images")
        
        print(f"Location: {output_path.absolute()}")
        
        # Generate summary info
        self._create_batch_summary(output_path, total_generated, total_size_mb, sizes, color_schemes, batch_size)
    
    @staticmethod
    def _canvases(sizes, width, height, shape):
        if shape not in SHAPES:
            raise ValueError(f'Unknown shape {shape!r}')
        if (width is None) != (height is None):
            raise ValueError('width and height must be supplied together')
        if width is not None:
            if sizes is not None:
                raise ValueError('Use sizes or width/height, not both')
            canvases = [(width, height)]
        else:
            if sizes is None:
                sizes = [512, 1024]
            if not sizes:
                raise ValueError('At least one size is required')
            canvases = [(size, size) for size in sizes]
        for w, h in canvases:
            if any(isinstance(v, bool) or not isinstance(v, int) or not 64 <= v <= 4096
                   for v in (w, h)):
                raise ValueError('Batch dimensions must be integers between 64 and 4096 pixels')
            if shape == 'circle' and w != h:
                raise ValueError('Circles require equal width and height')
        return canvases

    def generate_parameter_exploration(self, output_dir: str, base_colors: List[str] = None,
                                      parameter_steps: int = 5, *, shape: str = 'circle',
                                      width: Optional[int] = None, height: Optional[int] = None,
                                      sizes: Optional[List[int]] = None) -> None:
        """Explore texture parameters on the selected shapes and canvas sizes.

        Without dimensions or sizes this retains the original 512px canvas.
        New shapes apply each named parameter; legacy circle output is retained.
        """
        if parameter_steps < 2:
            raise ValueError('parameter_steps must be at least 2')
        if sizes is None and width is None and height is None:
            sizes = [512]
        canvases = self._canvases(sizes, width, height, shape)
        if base_colors is None:
            base_colors = ['#8B4513', '#D2691E', '#F4A460', '#DEB887', '#F5DEB3']
        MarbleStyle('Validate palette', base_colors)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        series = [
            ('vein_intensity', [0.3 + i / (parameter_steps - 1) for i in range(parameter_steps)], 1000, '.2f'),
            ('vein_scale', [0.010 + i * 0.020 / (parameter_steps - 1) for i in range(parameter_steps)], 2000, '.3f'),
            ('complexity', [2, 3, 4, 5], 3000, 'd'),
            ('texture_scale', [0.5 + i * 1.5 / (parameter_steps - 1) for i in range(parameter_steps)], 4000, '.2f'),
        ]
        total = 0
        for w, h in canvases:
            for parameter, values, seed_base, format_spec in series:
                for i, value in enumerate(values):
                    # Retain the historical seeds and filenames for circles.
                    seed = seed_base + (value if parameter == 'complexity' else i)
                    generator = MarbleGenerator(width=w, height=h, seed=seed)
                    if shape == 'circle':
                        image = generator.generate_marble_circle(custom_colors=base_colors)
                    else:
                        style = MarbleStyle('Parameter study', base_colors, vein_intensity=0.5,
                                            vein_scale=0.018, complexity=3)
                        setattr(style, parameter, value)
                        image = generator.generate_marble(shape, custom_style=style)
                    name = f'{parameter}_{value:{format_spec}}'
                    if shape != 'circle' or len(canvases) > 1:
                        name += f'_{shape}_{w}x{h}'
                    path = save_png(image, output_path / f'{name}.png')
                    print(f'  Created: {path}')
                    total += 1
        print(f'Parameter exploration complete: {total} images.')

    def _create_batch_summary(self, output_path: Path, total_generated: int, 
                             total_size_mb: float, sizes: List[int], 
                             color_schemes: List[str], batch_size: int) -> None:
        """Create a summary file for the generated batch."""
        summary_path = unused_path(output_path / "batch_summary.txt")
        
        with open(summary_path, 'x', encoding='utf-8') as f:
            f.write("Random Marble Generation Batch Summary\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Total Images Generated: {total_generated}\n")
            f.write(f"Total Size: {total_size_mb:.1f} MB\n")
            f.write(f"Average Size: {total_size_mb/total_generated:.2f} MB per image\n\n")
            f.write(f"Image Sizes: {sizes}\n")
            f.write(f"Batch Size per Size: {batch_size}\n")
            f.write(f"Color Schemes Used: {color_schemes}\n\n")
            f.write("Generated files include random variations of:\n")
            f.write("- Color palettes (3-6 colors per marble)\n")
            f.write("- Vein intensity (0.3-1.2)\n")
            f.write("- Vein scale (0.010-0.030)\n")
            f.write("- Complexity levels (2-5)\n")
            f.write("- Texture scale (0.5-2.0)\n")
            f.write("- Intensity multipliers (0.8-1.2)\n\n")
            f.write("Filename format: {scheme}_{size}px_{number}_{timestamp}_i{intensity}_s{seed}.png\n")
            f.write("Note: New images are appended to existing collections without overwriting.\n")
        
        print(f"Summary saved: {summary_path}")


def main():
    """Main function with command-line interface."""
    parser = argparse.ArgumentParser(
        description="Generate random marble textures with varied parameters",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python random_marble_generator.py --batch-size 15 --sizes 512,1024,2048
  python random_marble_generator.py --explore-parameters --output ./param_test/
  python random_marble_generator.py --schemes analogous,complementary --batch-size 20
  python random_marble_generator.py --custom-colors "#8B4513,#D2691E,#F4A460" --batch-size 10
        """
    )
    
    parser.add_argument('--output', default='./random_marbles/',
                       help='Output directory (default: ./random_marbles/)')
    parser.add_argument('--batch-size', type=int, default=10,
                       help='Number of marbles per size (default: 10)')
    parser.add_argument('--sizes', type=str, default=None,
                       help='Comma-separated image sizes (default: 256,512,1024,2048)')
    parser.add_argument('--shape', choices=SHAPES, default='circle')
    parser.add_argument('--width', type=int, help='Canvas width; requires --height')
    parser.add_argument('--height', type=int, help='Canvas height; requires --width')
    parser.add_argument('--schemes', type=str,
                       default='random,analogous,complementary,triadic,monochromatic',
                       help='Comma-separated color schemes')
    parser.add_argument('--intensity-min', type=float, default=0.8,
                       help='Minimum intensity (default: 0.8)')
    parser.add_argument('--intensity-max', type=float, default=1.2,
                       help='Maximum intensity (default: 1.2)')
    parser.add_argument('--seed', type=int,
                       help='Random seed for reproducible results')
    parser.add_argument('--explore-parameters', action='store_true',
                       help='Generate parameter exploration instead of random batch')
    parser.add_argument('--custom-colors', type=str,
                       help='Custom base colors for parameter exploration (comma-separated hex)')
    
    args = parser.parse_args()
    
    # Explicit dimensions replace the default sizes, never an explicit list.
    try:
        sizes = [int(s.strip()) for s in args.sizes.split(',')] if args.sizes is not None else None
        if sizes is None and args.width is None and args.height is None and not args.explore_parameters:
            sizes = [256, 512, 1024, 2048]
        RandomMarbleGenerator._canvases(sizes, args.width, args.height, args.shape)
        if args.batch_size < 1:
            raise ValueError('batch-size must be a positive integer')
    except ValueError as error:
        parser.error(str(error))

    # Parse color schemes
    valid_schemes = {'random', 'analogous', 'complementary', 'triadic', 'monochromatic'}
    schemes = [s.strip() for s in args.schemes.split(',')]
    for scheme in schemes:
        if scheme not in valid_schemes:
            print(f"Error: Unknown color scheme '{scheme}'. Valid: {valid_schemes}")
            sys.exit(1)
    
    # Parse custom colors if provided
    custom_colors = None
    if args.custom_colors:
        try:
            custom_colors = [color.strip() for color in args.custom_colors.split(',')]
            MarbleStyle('Custom', custom_colors)
            if len(custom_colors) < 2:
                print("Error: At least 2 colors required for custom palette")
                sys.exit(1)
        except Exception as e:
            print(f"Error parsing custom colors: {e}")
            sys.exit(1)
    
    # Validate intensity range
    if not (math.isfinite(args.intensity_min) and math.isfinite(args.intensity_max)
            and 0.1 <= args.intensity_min < args.intensity_max <= 2.0):
        print("Error: Intensity range must satisfy 0.1 <= min < max <= 2.0")
        sys.exit(1)
    
    # Create generator
    generator = RandomMarbleGenerator(seed=args.seed)
    
    if args.explore_parameters:
        # Parameter exploration mode
        generator.generate_parameter_exploration(
            output_dir=args.output,
            base_colors=custom_colors, shape=args.shape,
            width=args.width, height=args.height, sizes=sizes
        )
    else:
        # Random batch generation mode
        generator.generate_marble_batch(
            output_dir=args.output,
            batch_size=args.batch_size,
            sizes=sizes,
            color_schemes=schemes,
            intensity_range=(args.intensity_min, args.intensity_max),
            shape=args.shape, width=args.width, height=args.height
        )
    
    print(f"\nGeneration complete!")
    print(f"Random marble textures ready in: {args.output}")


if __name__ == "__main__":
    main() 