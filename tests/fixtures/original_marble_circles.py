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
    
    def __init__(self, size: int = 1024, seed: Optional[int] = None):
        """Initialize the marble generator.
        
        Args:
            size: Output image size (square)
            seed: Random seed for reproducible results
        """
        self.size = size
        self.center = size // 2
        self.radius = size // 2 - 10  # Slight padding for anti-aliasing
        
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)
        
        # Generate random offsets for noise functions
        self.noise_offsets = [
            (random.uniform(0, 1000), random.uniform(0, 1000)) 
            for _ in range(6)
        ]
    
    def _generate_base_noise(self, style: MarbleStyle) -> np.ndarray:
        """Generate base Perlin noise pattern."""
        noise_array = np.zeros((self.size, self.size))
        
        for i in range(self.size):
            for j in range(self.size):
                # Multiple octaves of noise for complexity
                noise_val = 0
                for octave in range(style.complexity):
                    freq = style.vein_scale * (2 ** octave) * style.texture_scale
                    amp = 1.0 / (2 ** octave)
                    offset_x, offset_y = self.noise_offsets[octave % len(self.noise_offsets)]
                    
                    noise_val += amp * pnoise2(
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
        noise_array = np.zeros((self.size, self.size))
        
        # Define dramatic rotation strengths for each planet type - much stronger effects
        rotation_strengths = {
            'jupiter': 3.0, 'earth': 2.0, 'mars': 1.8, 'alien': 2.5,
            'volcanic': 2.2, 'ice_world': 1.5, 'ocean_world': 2.0, 'desert': 1.8
        }
        rotation_strength = rotation_strengths.get(planet_type, 0.4)
        
        for i in range(self.size):
            for j in range(self.size):
                # Get dramatically horizontally-flowing coordinates for marble patterns
                dist_from_center_y = abs(i - self.center) / self.radius
                latitude_factor = 1.0 - (dist_from_center_y ** 0.4)  # Sharper falloff
                rotation_factor = latitude_factor * rotation_strength
                
                # Create DRAMATIC horizontal flow for marble veins - much stronger
                primary_flow = pnoise2(i * 0.003 * style.texture_scale, j * 0.001 * style.texture_scale, octaves=2, base=5000) * 180 * rotation_factor
                secondary_flow = pnoise2(i * 0.008 * style.texture_scale, j * 0.002 * style.texture_scale, octaves=1, base=5100) * 100 * rotation_factor
                
                # Combine for very visible horizontal marble streaming
                total_flow = primary_flow + secondary_flow
                flow_j = j + total_flow
                
                # Multiple octaves of noise for complexity using flowing coordinates
                noise_val = 0
                for octave in range(style.complexity):
                    freq = style.vein_scale * (2 ** octave) * style.texture_scale
                    amp = 1.0 / (2 ** octave)
                    offset_x, offset_y = self.noise_offsets[octave % len(self.noise_offsets)]
                    
                    noise_val += amp * pnoise2(
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
        vein_noise = np.zeros((self.size, self.size))
        
        for i in range(self.size):
            for j in range(self.size):
                # Create flowing, directional patterns
                x_flow = pnoise2(i * 0.008 * style.texture_scale, j * 0.008 * style.texture_scale, base=100) * 50
                y_flow = pnoise2(i * 0.012 * style.texture_scale, j * 0.006 * style.texture_scale, base=200) * 30
                
                # Sample noise along the flow direction
                flow_x = i + x_flow
                flow_y = j + y_flow
                
                vein_val = pnoise2(
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
        pattern = np.zeros((self.size, self.size))
        
        # Add dramatic rotational flow by modifying noise sampling coordinates
        def get_rotational_coordinates(i, j, rotation_strength=0.5):
            """Get dramatically horizontally-flowing coordinates for visible marble streaming."""
            # Distance from center affects rotation speed (faster at equator)
            dist_from_center_y = abs(i - self.center) / self.radius
            
            # Create smooth latitude zones with dramatic falloff
            latitude_factor = 1.0 - (dist_from_center_y ** 0.4)  # Sharper falloff for more drama
            rotation_factor = latitude_factor * rotation_strength
            
            # Create DRAMATIC horizontal flow displacement - much stronger effect
            primary_flow = pnoise2(i * 0.003 * style.texture_scale, j * 0.001 * style.texture_scale, octaves=2, base=2000) * 150 * rotation_factor
            secondary_flow = pnoise2(i * 0.008 * style.texture_scale, j * 0.002 * style.texture_scale, octaves=1, base=2100) * 80 * rotation_factor
            
            # Combine flows for very visible horizontal streaming
            total_flow = primary_flow + secondary_flow
            
            # Apply dramatic horizontal displacement to j coordinate
            flow_j = j + total_flow
            
            # Return the modified coordinates for noise sampling
            return i, flow_j
        
        if planet_type in ['earth', 'ocean_world']:
            # Generate continent/ocean patterns with dramatic horizontal flow
            for i in range(self.size):
                for j in range(self.size):
                    # Get dramatically flowing coordinates - very strong effect
                    flow_i, flow_j = get_rotational_coordinates(i, j, 2.0)
                    
                    # Large-scale landmass patterns using flowing coordinates
                    continent = pnoise2(flow_i * 0.006 * style.texture_scale, flow_j * 0.006 * style.texture_scale, octaves=3, base=400)
                    # Weather systems with horizontal flow
                    weather = pnoise2(flow_i * 0.015 * style.texture_scale, flow_j * 0.012 * style.texture_scale, octaves=2, base=500) * 0.3
                    pattern[i, j] = continent + weather
                    
        elif planet_type == 'jupiter':
            # Gas giant with dramatically flowing banding patterns
            for i in range(self.size):
                for j in range(self.size):
                    # Get dramatically flowing coordinates - very strong gas giant effect
                    flow_i, flow_j = get_rotational_coordinates(i, j, 3.0)
                    
                    # Horizontal bands with flowing marble patterns
                    lat_bands = math.sin((flow_i - self.center) * 0.025 * style.texture_scale) * 0.8
                    # Turbulence using flowing coordinates
                    turbulence = pnoise2(flow_i * 0.008 * style.texture_scale, flow_j * 0.025 * style.texture_scale, octaves=4, base=600) * 0.4
                    pattern[i, j] = lat_bands + turbulence
                    
        elif planet_type in ['mars', 'desert']:
            # Desert/rocky terrain with dramatic horizontal dust patterns
            for i in range(self.size):
                for j in range(self.size):
                    # Get dramatically flowing coordinates - strong dust storm effect
                    flow_i, flow_j = get_rotational_coordinates(i, j, 1.8)
                    
                    # Terrain features with horizontal flow
                    terrain = pnoise2(flow_i * 0.010 * style.texture_scale, flow_j * 0.010 * style.texture_scale, octaves=3, base=800)
                    # Dust storm patterns flowing horizontally
                    dust = pnoise2(flow_i * 0.020 * style.texture_scale, flow_j * 0.008 * style.texture_scale, octaves=2, base=900) * 0.4
                    pattern[i, j] = terrain + dust
                    
        elif planet_type == 'ice_world':
            # Ice sheets with dramatic horizontal wind patterns
            for i in range(self.size):
                for j in range(self.size):
                    # Get dramatically flowing coordinates - strong wind effect
                    flow_i, flow_j = get_rotational_coordinates(i, j, 1.5)
                    
                    # Ice formations with horizontal flow
                    ice = pnoise2(flow_i * 0.012 * style.texture_scale, flow_j * 0.012 * style.texture_scale, octaves=2, base=1000)
                    # Wind-carved patterns flowing horizontally
                    wind_patterns = pnoise2(flow_i * 0.025 * style.texture_scale, flow_j * 0.015 * style.texture_scale, octaves=1, base=1100) * 0.3
                    pattern[i, j] = ice + wind_patterns
                    
        elif planet_type == 'volcanic':
            # Lava flows with dramatic horizontal patterns
            for i in range(self.size):
                for j in range(self.size):
                    # Get dramatically flowing coordinates - strong lava flow effect
                    flow_i, flow_j = get_rotational_coordinates(i, j, 2.2)
                    
                    # Lava channels flowing horizontally
                    lava = pnoise2(flow_i * 0.008 * style.texture_scale, flow_j * 0.015 * style.texture_scale, octaves=3, base=1200)
                    # Volcanic hotspots with horizontal patterns
                    hotspots = pnoise2(flow_i * 0.030 * style.texture_scale, flow_j * 0.030 * style.texture_scale, octaves=1, base=1300) * 0.6
                    pattern[i, j] = lava + hotspots
                    
        elif planet_type == 'alien':
            # Exotic alien patterns with dramatic horizontal energy flows
            for i in range(self.size):
                for j in range(self.size):
                    # Get dramatically flowing coordinates - strong alien energy effect
                    flow_i, flow_j = get_rotational_coordinates(i, j, 2.5)
                    
                    # Strange formations with horizontal flow
                    alien1 = pnoise2(flow_i * 0.014 * style.texture_scale, flow_j * 0.014 * style.texture_scale, octaves=4, base=1400)
                    # Energy patterns flowing horizontally
                    alien2 = pnoise2(flow_i * 0.022 * style.texture_scale, flow_j * 0.009 * style.texture_scale, octaves=2, base=1500) * 0.4
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
    
    def generate_marble_circle(self, style_name: str = 'carrara', 
                              custom_colors: Optional[List[str]] = None,
                              intensity: float = 1.0) -> Image.Image:
        """Generate a marblized circle image.
        
        Args:
            style_name: Name of predefined style or 'custom'
            custom_colors: List of hex colors for custom style
            intensity: Intensity multiplier for effects (0.1 to 2.0)
            
        Returns:
            PIL Image with marble circle
        """
        # Get or create marble style
        if custom_colors:
            style = MarbleStyle('Custom', custom_colors, 
                              vein_intensity=0.6 * intensity, 
                              vein_scale=0.016)
        else:
            if style_name not in self.MARBLE_STYLES:
                print(f"Warning: Style '{style_name}' not found. Using 'carrara'.")
                style_name = 'carrara'
            style = self.MARBLE_STYLES[style_name]
            # Apply intensity scaling
            style.vein_intensity *= intensity
        
        print(f"Generating {style.name} texture...")
        
        # Check if this is a planetary style
        planetary_styles = ['earth', 'mars', 'jupiter', 'ice_world', 'desert', 'volcanic', 'ocean_world', 'alien']
        is_planetary = style_name in planetary_styles
        
        # Generate noise patterns with horizontal flow for planets
        if is_planetary:
            base_noise = self._generate_horizontal_base_noise(style, style_name)
        else:
            base_noise = self._generate_base_noise(style)
        
        if is_planetary:
            vein_noise = self._generate_planetary_pattern(style, style_name)
        else:
            vein_noise = self._generate_vein_pattern(style)
        
        # Create the marble texture
        image_array = np.zeros((self.size, self.size, 3), dtype=np.uint8)
        
        for i in range(self.size):
            for j in range(self.size):
                # Blend colors based on noise patterns
                color = self._blend_colors(
                    style.colors,
                    base_noise[i, j],
                    vein_noise[i, j] * style.vein_intensity
                )
                image_array[i, j] = color
        
        # Convert to PIL Image
        marble_image = Image.fromarray(image_array, 'RGB')
        
        # Add slight blur for smoothness
        marble_image = marble_image.filter(ImageFilter.GaussianBlur(radius=0.5))
        
        # Convert to RGBA for transparency
        marble_image = marble_image.convert('RGBA')
        
        # Apply circular mask
        mask = self._create_circle_mask()
        marble_image.putalpha(mask)
        
        # Apply lighting effects
        if is_planetary:
            # Apply atmospheric glow for planets
            marble_image = self._apply_atmospheric_glow(marble_image, style_name)
        else:
            # Apply regular lighting for marble
            marble_image = self._apply_lighting(marble_image)
        
        # Enhance contrast and saturation slightly
        enhancer = ImageEnhance.Contrast(marble_image)
        marble_image = enhancer.enhance(1.1)
        
        enhancer = ImageEnhance.Color(marble_image)
        marble_image = enhancer.enhance(1.05)
        
        return marble_image


def parse_colors(color_string: str) -> List[str]:
    """Parse comma-separated color string."""
    return [color.strip() for color in color_string.split(',')]


def main():
    """Main function with command-line interface."""
    parser = argparse.ArgumentParser(
        description="Generate beautiful marblized circle PNG images",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python marble_circles.py --style carrara --size 2048 --count 5
  python marble_circles.py --colors "#2C3E50,#34495E,#ECF0F1" --intensity 0.7
  python marble_circles.py --style golden --output ./marble_art/ --seed 12345
  python marble_circles.py --list-styles
        """
    )
    
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
    
    # Validate parameters
    if args.size < 64 or args.size > 8192:
        print("Error: Size must be between 64 and 8192 pixels")
        sys.exit(1)
    
    if args.intensity < 0.1 or args.intensity > 2.0:
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
            if len(custom_colors) < 2:
                print("Error: At least 2 colors required for custom palette")
                sys.exit(1)
        except Exception as e:
            print(f"Error parsing colors: {e}")
            sys.exit(1)
    
    # Create output directory
    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)
    
    print(f"Generating {args.count} marble circle(s)...")
    print(f"Style: {args.style if not custom_colors else 'custom'}")
    print(f"Size: {args.size}x{args.size} pixels")
    print(f"Output: {output_path}")
    
    # Generate images
    for i in range(args.count):
        # Use different seeds for each image if no seed specified
        current_seed = args.seed
        if current_seed is None and args.count > 1:
            current_seed = random.randint(1, 1000000)
        
        generator = MarbleGenerator(size=args.size, seed=current_seed)
        
        image = generator.generate_marble_circle(
            style_name=args.style,
            custom_colors=custom_colors,
            intensity=args.intensity
        )
        
        # Generate filename
        if args.count == 1:
            filename = f"{args.prefix}.png"
        else:
            filename = f"{args.prefix}_{i+1:03d}.png"
        
        filepath = output_path / filename
        
        # Save image
        image.save(filepath, 'PNG', optimize=True)
        print(f"  Created: {filepath}")
        
        if current_seed is not None:
            print(f"    Seed: {current_seed}")
    
    print(f"\nSuccessfully generated {args.count} marble circle(s)!")
    print(f"Total file size: {sum(f.stat().st_size for f in output_path.glob('*.png')) / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main() 