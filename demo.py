#!/usr/bin/env python3
"""
Demo script for the Beautiful Marblized Circle PNG Generator

This script demonstrates various marble styles and generates sample images
to showcase the capabilities of the marble circle generator.
"""

import os
import sys
from pathlib import Path
from marble_circles import MarbleGenerator
from marble_shapes import save_png

def create_demo_gallery():
    """Create a gallery of demo marble circles."""
    
    # Create demo output directory
    demo_dir = Path("./demo_gallery")
    demo_dir.mkdir(exist_ok=True)
    
    print("Creating Marble Circle Demo Gallery...")
    print("=" * 50)
    
    # Demo configurations
    demos = [
        {"style": "carrara", "size": 512, "description": "Classic Carrara White Marble"},
        {"style": "black", "size": 512, "description": "Elegant Black Marble"},
        {"style": "green", "size": 512, "description": "Natural Green Serpentine"},
        {"style": "pink", "size": 512, "description": "Delicate Pink Marble"},
        {"style": "blue", "size": 512, "description": "Ocean Blue Marble"},
        {"style": "golden", "size": 512, "description": "Luxurious Golden Marble"},
        {"style": "burgundy", "size": 512, "description": "Rich Burgundy Marble"},
    ]
    
    # Generate demo images
    for i, demo in enumerate(demos, 1):
        print(f"\n[{i}/{len(demos)}] {demo['description']}")
        
        generator = MarbleGenerator(size=demo['size'], seed=12345)  # Fixed seed for consistency
        
        image = generator.generate_marble_circle(
            style_name=demo['style'],
            intensity=1.0
        )
        
        filename = f"{demo['style']}_marble_demo.png"
        filepath = demo_dir / filename
        
        filepath = save_png(image, filepath)
        filename = filepath.name
        file_size = filepath.stat().st_size / 1024  # KB
        
        print(f"  Saved: {filename} ({file_size:.1f} KB)")
    
    # Create a high-resolution showcase
    print(f"\n[BONUS] High-Resolution Showcase (2048x2048)")
    generator = MarbleGenerator(size=2048, seed=54321)
    
    image = generator.generate_marble_circle(
        style_name="golden",
        intensity=1.2
    )
    
    hires_path = demo_dir / "golden_marble_hires_showcase.png"
    hires_path = save_png(image, hires_path)
    file_size = hires_path.stat().st_size / 1024 / 1024  # MB
    
    print(f"  Saved: {hires_path.name} ({file_size:.1f} MB)")
    
    # Create custom color demonstration
    print(f"\n[CUSTOM] Custom Color Palette Demo")
    generator = MarbleGenerator(size=512, seed=99999)
    
    custom_colors = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4"]
    
    image = generator.generate_marble_circle(
        custom_colors=custom_colors,
        intensity=0.8
    )
    
    custom_path = demo_dir / "custom_colors_demo.png"
    custom_path = save_png(image, custom_path)
    file_size = custom_path.stat().st_size / 1024  # KB
    
    print(f"  Saved: {custom_path.name} ({file_size:.1f} KB)")
    
    print("\n" + "=" * 50)
    print("Demo Gallery Complete!")
    print(f"Location: {demo_dir.absolute()}")
    print(f"Total Images: {len(list(demo_dir.glob('*.png')))}")
    total_size = sum(f.stat().st_size for f in demo_dir.glob('*.png')) / 1024 / 1024
    print(f"Total Size: {total_size:.1f} MB")
    
    print("\nUsage Examples:")
    print("  View the demo images to see different marble styles")
    print("  Use these as reference for your own creations")
    print("  Experiment with different parameters and styles")


def show_available_styles():
    """Display available marble styles with color information."""
    
    print("Available Marble Styles:")
    print("=" * 50)
    
    for name, style in MarbleGenerator.MARBLE_STYLES.items():
        colors_hex = [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in style.colors]
        print(f"  {name:10} | Colors: {', '.join(colors_hex)}")
        print(f"             | Intensity: {style.vein_intensity:.1f} | Scale: {style.vein_scale:.3f}")
        print()


if __name__ == "__main__":
    print("Beautiful Marblized Circle PNG Generator - Demo")
    print("=" * 50)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--styles":
        show_available_styles()
    else:
        create_demo_gallery() 