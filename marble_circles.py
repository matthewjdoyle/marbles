#!/usr/bin/env python3
"""
Beautiful Marblized Circle PNG Generator

A sophisticated tool for creating stunning marble-textured circular artwork
with realistic stone patterns, professional quality output, and extensive
customization options.

Author: AI Assistant
Version: 1.0
"""

import argparse
from copy import deepcopy
import os
import sys
import random
from pathlib import Path
from typing import List, Tuple, Dict, Optional
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
from noise import pnoise2, pnoise3
import colorsys
from marble_shapes import SHAPES, shape_mask, save_png


class MarbleStyle:
    """Defines a marble style with colors and texture parameters."""
    
    def __init__(self, name: str, colors: List[str], vein_intensity: float = 0.6,
                 vein_scale: float = 0.02, complexity: int = 3, texture_scale: float = 1.0):
        self.name = name
        self.colors = [self._hex_to_rgb(c) for c in colors]
        self.vein_intensity = vein_intensity
        self.vein_scale = vein_scale
        self.complexity = complexity
        self.texture_scale = texture_scale  # Controls overall size of texture elements
    
    @staticmethod
    def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color to RGB tuple."""
        hex_color = hex_color.lstrip('#')
        if len(hex_color) != 6 or any(c not in '0123456789abcdefABCDEF' for c in hex_color):
            raise ValueError('Colors must contain exactly six hexadecimal digits, e.g. #4ECDC4')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


class MarbleGenerator:
    """Advanced marble texture generator using Perlin noise."""
    
    # Predefined marble styles
    MARBLE_STYLES = {
        'carrara': MarbleStyle('Carrara White', 
                              ['#F8F8FF', '#F0F0F0', '#E8E8E8', '#D3D3D3'], 
                              vein_intensity=0.4, vein_scale=0.015),
        'black': MarbleStyle('Black Marble', 
                            ['#2C2C2C', '#1A1A1A', '#404040', '#595959'], 
                            vein_intensity=0.6, vein_scale=0.02),
        'green': MarbleStyle('Green Serpentine', 
                            ['#2D5016', '#3D6B1A', '#4A7C59', '#6B8E23'], 
                            vein_intensity=0.7, vein_scale=0.018),
        'pink': MarbleStyle('Pink Marble', 
                           ['#F5DEB3', '#DDA0DD', '#DA70D6', '#CD919E'], 
                           vein_intensity=0.5, vein_scale=0.016),
        'blue': MarbleStyle('Blue Marble', 
                           ['#4682B4', '#5F9EA0', '#6495ED', '#87CEEB'], 
                           vein_intensity=0.6, vein_scale=0.017),
        'golden': MarbleStyle('Golden Marble', 
                             ['#FFD700', '#FFA500', '#DAA520', '#B8860B'], 
                             vein_intensity=0.5, vein_scale=0.014),
        'burgundy': MarbleStyle('Burgundy Marble', 
                               ['#800020', '#A0232C', '#C0392B', '#DC381F'], 
                               vein_intensity=0.7, vein_scale=0.019),
        
        # Planetary Styles
        'earth': MarbleStyle('Earth Planet', 
                            ['#1E3A8A', '#3B82F6', '#10B981', '#059669', '#F0F9FF'], 
                            vein_intensity=0.8, vein_scale=0.025, complexity=4),
        'mars': MarbleStyle('Mars Planet', 
                           ['#DC2626', '#EA580C', '#F59E0B', '#FCD34D', '#451A03'], 
                           vein_intensity=0.6, vein_scale=0.022, complexity=3),
        'jupiter': MarbleStyle('Gas Giant', 
                              ['#F59E0B', '#D97706', '#92400E', '#FEF3C7', '#78350F'], 
                              vein_intensity=0.9, vein_scale=0.012, complexity=5),
        'ice_world': MarbleStyle('Ice World', 
                                ['#DBEAFE', '#BFDBFE', '#93C5FD', '#3B82F6', '#F8FAFC'], 
                                vein_intensity=0.5, vein_scale=0.020, complexity=3),
        'desert': MarbleStyle('Desert Planet', 
                             ['#FED7AA', '#FDBA74', '#FB923C', '#EA580C', '#9A3412'], 
                             vein_intensity=0.7, vein_scale=0.018, complexity=4),
        'volcanic': MarbleStyle('Volcanic World', 
                               ['#7F1D1D', '#DC2626', '#F97316', '#FBBF24', '#1F2937'], 
                               vein_intensity=1.0, vein_scale=0.015, complexity=4),
        'ocean_world': MarbleStyle('Ocean World', 
                                  ['#0C4A6E', '#0369A1', '#0284C7', '#38BDF8', '#F0F9FF'], 
                                  vein_intensity=0.6, vein_scale=0.024, complexity=3),
        'alien': MarbleStyle('Alien World', 
                            ['#581C87', '#7C3AED', '#A855F7', '#C084FC', '#1F2937'], 
                            vein_intensity=0.8, vein_scale=0.016, complexity=4)
    }
    
    def __init__(self, size: int = 1024, seed: Optional[int] = None, *,
                 width: Optional[int] = None, height: Optional[int] = None):
        """Initialize the marble generator.
        
        Args:
            size: Output image size (square)
            seed: Random seed for reproducible results
            width, height: Explicit canvas dimensions; both override size
        """
        if (width is None) != (height is None):
            raise ValueError('width and height must be supplied together')
        width, height = (size, size) if width is None else (width, height)
        if any(isinstance(v, bool) or not isinstance(v, int) or not 64 <= v <= 8192
               for v in (width, height)):
            raise ValueError('Dimensions must be integers between 64 and 8192 pixels')
        self.width, self.height = width, height
        self._legacy_noise = True
        self.size = width  # Legacy square-circle attributes.
        self.center = width // 2
        self.radius = width // 2 - 10  # Slight padding for anti-aliasing
        
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)
        
        # Generate random offsets for noise functions
        self.noise_offsets = [
            (random.uniform(0, 1000), random.uniform(0, 1000)) 
            for _ in range(6)
        ]
    
    def _noise(self, x, y, **options):
        # noise 1.2.2 adds base to permutation-table indices without wrapping.
        # Legacy circles retain their original sampling for compatibility.
        # New shapes use base=0 and translate coordinates to distinguish fields;
        # this stays within the lookup table and is stable across processes.
        if not self._legacy_noise:
            base = options.pop('base', 0)
            x += base * 0.137
            y += base * 0.173
            options['base'] = 0
        return pnoise2(x, y, **options)

    def _generate_base_noise(self, style: MarbleStyle) -> np.ndarray:
        """Generate base Perlin noise pattern."""
        noise_array = np.zeros((self.height, self.width))
        
        for i in range(self.height):
            for j in range(self.width):
                # Multiple octaves of noise for complexity
                noise_val = 0
                for octave in range(style.complexity):
                    freq = style.vein_scale * (2 ** octave) * style.texture_scale
                    amp = 1.0 / (2 ** octave)
                    offset_x, offset_y = self.noise_offsets[octave % len(self.noise_offsets)]
                    
                    noise_val += amp * self._noise(
                        (i + offset_x) * freq,
                        (j + offset_y) * freq,
                        octaves=1,
                        persistence=0.5,
                        lacunarity=2.0,
                        repeatx=1024,
                        repeaty=1024,
                        base=42
                    )
                
                noise_array[i, j] = noise_val
        
        return noise_array
    
    def _generate_horizontal_base_noise(self, style: MarbleStyle, planet_type: str) -> np.ndarray:
        """Generate base noise with horizontal flow for planetary marble patterns."""
        noise_array = np.zeros((self.height, self.width))
        
        # Define dramatic rotation strengths for each planet type - much stronger effects
        rotation_strengths = {
            'jupiter': 3.0, 'earth': 2.0, 'mars': 1.8, 'alien': 2.5,
            'volcanic': 2.2, 'ice_world': 1.5, 'ocean_world': 2.0, 'desert': 1.8
        }
        rotation_strength = rotation_strengths.get(planet_type, 0.4)
        
        for i in range(self.height):
            for j in range(self.width):
                # Get dramatically horizontally-flowing coordinates for marble patterns
                dist_from_center_y = abs(i - self.height // 2) / (self.height // 2 - 10)
                latitude_factor = 1.0 - (dist_from_center_y ** 0.4)  # Sharper falloff
                rotation_factor = latitude_factor * rotation_strength
                
                # Create DRAMATIC horizontal flow for marble veins - much stronger
                primary_flow = self._noise(i * 0.003 * style.texture_scale, j * 0.001 * style.texture_scale, octaves=2, base=5000) * 180 * rotation_factor
                secondary_flow = self._noise(i * 0.008 * style.texture_scale, j * 0.002 * style.texture_scale, octaves=1, base=5100) * 100 * rotation_factor
                
                # Combine for very visible horizontal marble streaming
                total_flow = primary_flow + secondary_flow
                flow_j = j + total_flow
                
                # Multiple octaves of noise for complexity using flowing coordinates
                noise_val = 0
                for octave in range(style.complexity):
                    freq = style.vein_scale * (2 ** octave) * style.texture_scale
                    amp = 1.0 / (2 ** octave)
                    offset_x, offset_y = self.noise_offsets[octave % len(self.noise_offsets)]
                    
                    noise_val += amp * self._noise(
                        (i + offset_x) * freq,
                        (flow_j + offset_y) * freq,
                        octaves=1,
                        persistence=0.5,
                        lacunarity=2.0,
                        repeatx=1024,
                        repeaty=1024,
                        base=42
                    )
                
                noise_array[i, j] = noise_val
        
        return noise_array
    
    def _generate_vein_pattern(self, style: MarbleStyle) -> np.ndarray:
        """Generate flowing vein patterns."""
        vein_noise = np.zeros((self.height, self.width))
        
        for i in range(self.height):
            for j in range(self.width):
                # Create flowing, directional patterns
                x_flow = self._noise(i * 0.008 * style.texture_scale, j * 0.008 * style.texture_scale, base=100) * 50
                y_flow = self._noise(i * 0.012 * style.texture_scale, j * 0.006 * style.texture_scale, base=200) * 30
                
                # Sample noise along the flow direction
                flow_x = i + x_flow
                flow_y = j + y_flow
                
                vein_val = self._noise(
                    flow_x * style.vein_scale * 2 * style.texture_scale,
                    flow_y * style.vein_scale * 2 * style.texture_scale,
                    octaves=2,
                    persistence=0.7,
                    base=300
                )
                
                vein_noise[i, j] = vein_val
        
        return vein_noise
    
    def _generate_planetary_pattern(self, style: MarbleStyle, planet_type: str) -> np.ndarray:
        """Generate planetary-specific patterns with rotational effects."""
        pattern = np.zeros((self.height, self.width))
        
        # Add dramatic rotational flow by modifying noise sampling coordinates
        def get_rotational_coordinates(i, j, rotation_strength=0.5):
            """Get dramatically horizontally-flowing coordinates for visible marble streaming."""
            # Distance from center affects rotation speed (faster at equator)
            dist_from_center_y = abs(i - self.height // 2) / (self.height // 2 - 10)
            
            # Create smooth latitude zones with dramatic falloff
            latitude_factor = 1.0 - (dist_from_center_y ** 0.4)  # Sharper falloff for more drama
            rotation_factor = latitude_factor * rotation_strength
            
            # Create DRAMATIC horizontal flow displacement - much stronger effect
            primary_flow = self._noise(i * 0.003 * style.texture_scale, j * 0.001 * style.texture_scale, octaves=2, base=2000) * 150 * rotation_factor
            secondary_flow = self._noise(i * 0.008 * style.texture_scale, j * 0.002 * style.texture_scale, octaves=1, base=2100) * 80 * rotation_factor
            
            # Combine flows for very visible horizontal streaming
            total_flow = primary_flow + secondary_flow
            
            # Apply dramatic horizontal displacement to j coordinate
            flow_j = j + total_flow
            
            # Return the modified coordinates for noise sampling
            return i, flow_j
        
        if planet_type in ['earth', 'ocean_world']:
            # Generate continent/ocean patterns with dramatic horizontal flow
            for i in range(self.height):
                for j in range(self.width):
                    # Get dramatically flowing coordinates - very strong effect
                    flow_i, flow_j = get_rotational_coordinates(i, j, 2.0)
                    
                    # Large-scale landmass patterns using flowing coordinates
                    continent = self._noise(flow_i * 0.006 * style.texture_scale, flow_j * 0.006 * style.texture_scale, octaves=3, base=400)
                    # Weather systems with horizontal flow
                    weather = self._noise(flow_i * 0.015 * style.texture_scale, flow_j * 0.012 * style.texture_scale, octaves=2, base=500) * 0.3
                    pattern[i, j] = continent + weather
                    
        elif planet_type == 'jupiter':
            # Gas giant with dramatically flowing banding patterns
            for i in range(self.height):
                for j in range(self.width):
                    # Get dramatically flowing coordinates - very strong gas giant effect
                    flow_i, flow_j = get_rotational_coordinates(i, j, 3.0)
                    
                    # Horizontal bands with flowing marble patterns
                    lat_bands = math.sin((flow_i - self.height // 2) * 0.025 * style.texture_scale) * 0.8
                    # Turbulence using flowing coordinates
                    turbulence = self._noise(flow_i * 0.008 * style.texture_scale, flow_j * 0.025 * style.texture_scale, octaves=4, base=600) * 0.4
                    pattern[i, j] = lat_bands + turbulence
                    
        elif planet_type in ['mars', 'desert']:
            # Desert/rocky terrain with dramatic horizontal dust patterns
            for i in range(self.height):
                for j in range(self.width):
                    # Get dramatically flowing coordinates - strong dust storm effect
                    flow_i, flow_j = get_rotational_coordinates(i, j, 1.8)
                    
                    # Terrain features with horizontal flow
                    terrain = self._noise(flow_i * 0.010 * style.texture_scale, flow_j * 0.010 * style.texture_scale, octaves=3, base=800)
                    # Dust storm patterns flowing horizontally
                    dust = self._noise(flow_i * 0.020 * style.texture_scale, flow_j * 0.008 * style.texture_scale, octaves=2, base=900) * 0.4
                    pattern[i, j] = terrain + dust
                    
        elif planet_type == 'ice_world':
            # Ice sheets with dramatic horizontal wind patterns
            for i in range(self.height):
                for j in range(self.width):
                    # Get dramatically flowing coordinates - strong wind effect
                    flow_i, flow_j = get_rotational_coordinates(i, j, 1.5)
                    
                    # Ice formations with horizontal flow
                    ice = self._noise(flow_i * 0.012 * style.texture_scale, flow_j * 0.012 * style.texture_scale, octaves=2, base=1000)
                    # Wind-carved patterns flowing horizontally
                    wind_patterns = self._noise(flow_i * 0.025 * style.texture_scale, flow_j * 0.015 * style.texture_scale, octaves=1, base=1100) * 0.3
                    pattern[i, j] = ice + wind_patterns
                    
        elif planet_type == 'volcanic':
            # Lava flows with dramatic horizontal patterns
            for i in range(self.height):
                for j in range(self.width):
                    # Get dramatically flowing coordinates - strong lava flow effect
                    flow_i, flow_j = get_rotational_coordinates(i, j, 2.2)
                    
                    # Lava channels flowing horizontally
                    lava = self._noise(flow_i * 0.008 * style.texture_scale, flow_j * 0.015 * style.texture_scale, octaves=3, base=1200)
                    # Volcanic hotspots with horizontal patterns
                    hotspots = self._noise(flow_i * 0.030 * style.texture_scale, flow_j * 0.030 * style.texture_scale, octaves=1, base=1300) * 0.6
                    pattern[i, j] = lava + hotspots
                    
        elif planet_type == 'alien':
            # Exotic alien patterns with dramatic horizontal energy flows
            for i in range(self.height):
                for j in range(self.width):
                    # Get dramatically flowing coordinates - strong alien energy effect
                    flow_i, flow_j = get_rotational_coordinates(i, j, 2.5)
                    
                    # Strange formations with horizontal flow
                    alien1 = self._noise(flow_i * 0.014 * style.texture_scale, flow_j * 0.014 * style.texture_scale, octaves=4, base=1400)
                    # Energy patterns flowing horizontally
                    alien2 = self._noise(flow_i * 0.022 * style.texture_scale, flow_j * 0.009 * style.texture_scale, octaves=2, base=1500) * 0.4
                    pattern[i, j] = alien1 + alien2
                    
        else:
            # Default to regular vein pattern
            return self._generate_vein_pattern(style)
            
        return pattern
    
    def _apply_atmospheric_glow(self, image: Image.Image, planet_type: str) -> Image.Image:
        """Apply atmospheric glow effects for planetary appearance."""
        glow = Image.new('RGBA', (self.size, self.size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(glow)
        
        # Define glow colors for different planet types
        glow_colors = {
            'earth': (135, 206, 235, 30),      # Sky blue
            'mars': (255, 69, 0, 25),          # Orange-red
            'jupiter': (255, 215, 0, 35),      # Golden
            'ice_world': (173, 216, 230, 20),  # Light blue
            'desert': (255, 140, 0, 20),       # Desert orange
            'volcanic': (255, 0, 0, 40),       # Red
            'ocean_world': (0, 191, 255, 25),  # Deep sky blue
            'alien': (138, 43, 226, 30)        # Purple
        }
        
        glow_color = glow_colors.get(planet_type, (255, 255, 255, 20))
        
        # Create atmospheric rim lighting
        for r in range(5, 25, 2):  # Multiple glow rings
            opacity = max(0, glow_color[3] * (1 - r / 25))
            if opacity > 0:
                bbox = [
                    self.center - self.radius - r,
                    self.center - self.radius - r,
                    self.center + self.radius + r,
                    self.center + self.radius + r
                ]
                color_with_opacity = glow_color[:3] + (int(opacity),)
                draw.ellipse(bbox, outline=color_with_opacity, width=2)
        
        # Blur the glow
        glow = glow.filter(ImageFilter.GaussianBlur(radius=8))
        
        # Blend with original image
        return Image.alpha_composite(image, glow)
    
    def _blend_colors(self, colors: List[Tuple[int, int, int]], 
                      noise_val: float, vein_val: float) -> Tuple[int, int, int]:
        """Blend colors based on noise values."""
        # Normalize noise values
        noise_val = (noise_val + 1) / 2  # Convert from [-1,1] to [0,1]
        vein_val = (vein_val + 1) / 2
        
        # Choose base color based on noise
        base_idx = int(noise_val * (len(colors) - 1))
        base_idx = max(0, min(base_idx, len(colors) - 1))
        
        # Create color variations
        base_color = colors[base_idx]
        
        # Apply vein effects
        vein_strength = abs(vein_val - 0.5) * 2  # Stronger at extremes
        
        # Darken/lighten based on vein pattern
        factor = 1.0 + (vein_val - 0.5) * 0.3
        
        r = int(np.clip(base_color[0] * factor, 0, 255))
        g = int(np.clip(base_color[1] * factor, 0, 255))
        b = int(np.clip(base_color[2] * factor, 0, 255))
        
        return (r, g, b)
    
    def _apply_lighting(self, image: Image.Image) -> Image.Image:
        """Apply subtle lighting effects for 3D appearance."""
        # Create a radial gradient for lighting
        gradient = Image.new('RGBA', (self.size, self.size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(gradient)
        
        # Multiple light sources for complex lighting
        light_positions = [
            (self.center - self.radius//3, self.center - self.radius//3),  # Top-left
            (self.center + self.radius//4, self.center + self.radius//4),  # Bottom-right (weaker)
        ]
        
        for pos_x, pos_y in light_positions:
            # Create radial gradient from light position
            for r in range(0, self.radius * 2, 10):
                opacity = max(0, int(30 * (1 - r / (self.radius * 1.5))))
                if opacity > 0:
                    bbox = [pos_x - r, pos_y - r, pos_x + r, pos_y + r]
                    draw.ellipse(bbox, fill=(255, 255, 255, opacity))
        
        # Blur the lighting layer
        gradient = gradient.filter(ImageFilter.GaussianBlur(radius=20))
        
        # Blend with original image
        return Image.alpha_composite(image, gradient)
    
    def _create_circle_mask(self) -> Image.Image:
        """Create a circular mask with anti-aliasing."""
        mask = Image.new('L', (self.size, self.size), 0)
        draw = ImageDraw.Draw(mask)
        
        # Draw circle with slight oversampling for anti-aliasing
        oversample = 4
        temp_size = self.size * oversample
        temp_mask = Image.new('L', (temp_size, temp_size), 0)
        temp_draw = ImageDraw.Draw(temp_mask)
        
        temp_center = temp_size // 2
        temp_radius = self.radius * oversample
        
        temp_draw.ellipse([
            temp_center - temp_radius,
            temp_center - temp_radius,
            temp_center + temp_radius,
            temp_center + temp_radius
        ], fill=255)
        
        # Resize back down for anti-aliasing
        mask = temp_mask.resize((self.size, self.size), Image.Resampling.LANCZOS)
        
        return mask
    
    def _generate_texture(self, style: MarbleStyle, style_name: str) -> Image.Image:
        """Render an unmasked texture at native canvas dimensions."""
        planetary = style_name in self.PLANETARY_STYLES
        base_noise = (self._generate_horizontal_base_noise(style, style_name)
                      if planetary else self._generate_base_noise(style))
        vein_noise = (self._generate_planetary_pattern(style, style_name)
                      if planetary else self._generate_vein_pattern(style))
        # Vectorized equivalent of _blend_colors, preserving its rounding and
        # arithmetic order. This avoids millions of Python calls for wallpapers.
        indices = ((base_noise + 1) / 2 * (len(style.colors) - 1)).astype(int)
        indices = np.clip(indices, 0, len(style.colors) - 1)
        colors = np.asarray(style.colors)[indices]
        veins = (vein_noise * style.vein_intensity + 1) / 2
        factors = 1.0 + (veins - 0.5) * 0.3
        pixels = np.clip(colors * factors[..., None], 0, 255).astype(np.uint8)
        return Image.fromarray(pixels).filter(
            ImageFilter.GaussianBlur(radius=0.5)).convert('RGBA')

    PLANETARY_STYLES = ('earth', 'mars', 'jupiter', 'ice_world', 'desert',
                        'volcanic', 'ocean_world', 'alien')

    def generate_marble(self, shape: str = 'circle', style_name: str = 'carrara',
                        custom_colors: Optional[List[str]] = None,
                        intensity: float = 1.0, *,
                        custom_style: Optional[MarbleStyle] = None,
                        deterministic_noise: bool = False,
                        corner_radius: float = .18, star_points: int = 5,
                        star_inner_ratio: float = .5) -> Image.Image:
        """Generate a circle, full-canvas rectangle, triangle, or flat-top hexagon.

        New shapes use flat lighting. Polygon exteriors are transparent. All
        shapes support the existing styles and custom palettes. custom_style
        exposes the full texture parameters for random batches and exploration.
        deterministic_noise uses safe, reproducible sampling for circles too;
        the default preserves legacy circle output for existing callers.
        """
        if shape not in SHAPES:
            raise ValueError(f'Unknown shape {shape!r}; choose from {SHAPES}')
        if shape == 'circle' and self.width != self.height:
            raise ValueError('Circles require equal width and height')
        if not math.isfinite(intensity) or not 0.1 <= intensity <= 2.0:
            raise ValueError('Intensity must be between 0.1 and 2.0')
        if custom_colors is not None and custom_style is not None:
            raise ValueError('Use custom_colors or custom_style, not both')
        if custom_style is not None:
            style = deepcopy(custom_style)
        elif custom_colors is not None:
            if len(custom_colors) < 2:
                raise ValueError('At least 2 colors required for custom palette')
            style = MarbleStyle('Custom', custom_colors, vein_intensity=0.6,
                                vein_scale=0.016)
        else:
            if style_name not in self.MARBLE_STYLES:
                print(f"Warning: Style '{style_name}' not found. Using 'carrara'.")
                style_name = 'carrara'
            style = deepcopy(self.MARBLE_STYLES[style_name])
        style.vein_intensity *= intensity
        print(f'Generating {style.name} {shape} texture...')
        self._legacy_noise = shape == 'circle' and not deterministic_noise
        image = self._generate_texture(style, style_name)
        if shape == 'circle':
            image.putalpha(self._create_circle_mask())
            if style_name in self.PLANETARY_STYLES:
                image = self._apply_atmospheric_glow(image, style_name)
            else:
                image = self._apply_lighting(image)
        # Preserve circle processing order; apply polygon alpha last to keep
        # enhancement or lighting from introducing a halo outside the shape.
        image = ImageEnhance.Contrast(image).enhance(1.1)
        image = ImageEnhance.Color(image).enhance(1.05)
        if shape not in ('circle', 'rectangle'):
            image.putalpha(shape_mask(shape, self.width, self.height,
                                      corner_radius=corner_radius, star_points=star_points,
                                      star_inner_ratio=star_inner_ratio))
        return image

    def generate_marble_circle(self, style_name: str = 'carrara',
                               custom_colors: Optional[List[str]] = None,
                               intensity: float = 1.0) -> Image.Image:
        """Compatible circle entry point, including original lighting and glow."""
        return self.generate_marble('circle', style_name, custom_colors, intensity)



def parse_colors(color_string: str) -> List[str]:
    """Parse comma-separated color string."""
    return [color.strip() for color in color_string.split(',')]


def main():
    """Main function with command-line interface."""
    parser = argparse.ArgumentParser(
        description="Generate marble circles, wallpapers, and polygon tile PNGs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python marble_circles.py --style carrara --size 2048 --count 5
  python marble_circles.py --colors "#2C3E50,#34495E,#ECF0F1" --intensity 0.7
  python marble_circles.py --style golden --output ./marble_art/ --seed 12345
  python marble_circles.py --list-styles
        """
    )
    
    parser.add_argument('--shape', choices=SHAPES, default='circle')
    parser.add_argument('--corner-radius', type=float, default=.18,
                        help='Rounded rectangle corner radius as a fraction of the shorter side (0–0.5)')
    parser.add_argument('--star-points', type=int, default=5, help='Star points (3–16)')
    parser.add_argument('--star-inner-ratio', type=float, default=.5,
                        help='Star inner radius divided by outer radius (0.1–0.9)')
    parser.add_argument('--width', type=int, help='Canvas width; requires --height')
    parser.add_argument('--height', type=int, help='Canvas height; requires --width')
    parser.add_argument('--style', default='carrara',
                       help='Style: carrara, black, green, pink, blue, golden, burgundy | Planets: earth, mars, jupiter, ice_world, desert, volcanic, ocean_world, alien')
    parser.add_argument('--colors', type=str,
                       help='Custom colors as comma-separated hex values (e.g., "#FF0000,#00FF00,#0000FF")')
    parser.add_argument('--size', type=int, default=1024,
                       help='Output image size in pixels (default: 1024)')
    parser.add_argument('--count', type=int, default=1,
                       help='Number of images to generate (default: 1)')
    parser.add_argument('--intensity', type=float, default=1.0,
                       help='Texture intensity (0.1 to 2.0, default: 1.0)')
    parser.add_argument('--seed', type=int,
                       help='Random seed for reproducible results')
    parser.add_argument('--output', default='./marble_output/',
                       help='Output directory (default: ./marble_output/)')
    parser.add_argument('--prefix', default='marble_circle',
                       help='Output filename prefix (default: marble_circle)')
    parser.add_argument('--list-styles', action='store_true',
                       help='List available marble styles')
    
    args = parser.parse_args()
    
    # List styles if requested
    if args.list_styles:
        print("Available marble styles:")
        for name, style in MarbleGenerator.MARBLE_STYLES.items():
            colors_hex = [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in style.colors]
            print(f"  {name:12} - {', '.join(colors_hex)}")
        return
    
    # Validate parameters before creating any output.
    try:
        canvas = MarbleGenerator(size=args.size, width=args.width, height=args.height, seed=args.seed)
        if args.shape == 'circle' and canvas.width != canvas.height:
            raise ValueError('Circles require equal width and height')
        if not math.isfinite(args.corner_radius) or not 0 <= args.corner_radius <= .5:
            raise ValueError('Corner radius must be between 0 and 0.5')
        if not 3 <= args.star_points <= 16:
            raise ValueError('Star points must be between 3 and 16')
        if not math.isfinite(args.star_inner_ratio) or not .1 <= args.star_inner_ratio <= .9:
            raise ValueError('Star inner radius ratio must be between 0.1 and 0.9')
    except ValueError as error:
        parser.error(str(error))
    if args.width is None and (args.size < 64 or args.size > 8192):
        print("Error: Size must be between 64 and 8192 pixels")
        sys.exit(1)
    
    if not math.isfinite(args.intensity) or args.intensity < 0.1 or args.intensity > 2.0:
        print("Error: Intensity must be between 0.1 and 2.0")
        sys.exit(1)
    
    if args.count < 1 or args.count > 100:
        print("Error: Count must be between 1 and 100")
        sys.exit(1)
    
    # Parse custom colors if provided
    custom_colors = None
    if args.colors:
        try:
            custom_colors = parse_colors(args.colors)
            MarbleStyle("Custom", custom_colors)
            if len(custom_colors) < 2:
                print("Error: At least 2 colors required for custom palette")
                sys.exit(1)
        except Exception as e:
            print(f"Error parsing colors: {e}")
            sys.exit(1)
    
    # Create output directory
    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)
    
    print(f"Generating {args.count} marble {args.shape}(s)...")
    print(f"Style: {args.style if not custom_colors else 'custom'}")
    print(f"Size: {canvas.width}x{canvas.height} pixels")
    print(f"Output: {output_path}")
    
    # Generate images
    for i in range(args.count):
        # Use different seeds for each image if no seed specified
        current_seed = args.seed
        if current_seed is None and args.count > 1:
            current_seed = random.randint(1, 1000000)
        
        generator = MarbleGenerator(size=args.size, seed=current_seed,
                                    width=args.width, height=args.height)
        
        image = generator.generate_marble(
            shape=args.shape, style_name=args.style,
            custom_colors=custom_colors,
            intensity=args.intensity, corner_radius=args.corner_radius,
            star_points=args.star_points, star_inner_ratio=args.star_inner_ratio
        )
        
        # Generate filename
        if args.count == 1:
            filename = f"{args.prefix}.png"
        else:
            filename = f"{args.prefix}_{i+1:03d}.png"
        
        if args.shape != 'circle':
            prefix = 'marble' if args.prefix == 'marble_circle' else args.prefix
            suffix = '' if args.count == 1 else f'_{i+1:03d}'
            filename = f'{prefix}_{args.shape}_{canvas.width}x{canvas.height}{suffix}.png'
        filepath = output_path / filename
        
        # Save image
        filepath = save_png(image, filepath)
        print(f"  Created: {filepath}")
        
        if current_seed is not None:
            print(f"    Seed: {current_seed}")
    
    print(f"\nSuccessfully generated {args.count} marble {args.shape}(s)!")
    print(f"Total file size: {sum(f.stat().st_size for f in output_path.glob('*.png')) / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main() 
