#!/usr/bin/env python3
"""
Enhanced USDZ Model Generator - Creates 3D USDZ files for augmented reality
Creates realistic 3D frame models with depth, sides, back panel, and hanging orientation
Based on the enhanced GLB implementation
"""

import sys
import json
import base64
import os
import zipfile
import tempfile
import shutil
import math
import random
from io import BytesIO
from PIL import Image

def create_enhanced_3d_usdz_from_image(image_data, width_meters, height_meters, depth_meters=0.008):
    """
    Creates an enhanced 3D USDZ file from an image with realistic frame structure.
    
    Args:
        image_data: Base64 encoded image data
        width_meters: Width in meters (will be overridden to 60" = 1.524m)
        height_meters: Height in meters (calculated from aspect ratio)
        depth_meters: Depth in meters (8mm = 0.008m)
    
    Returns:
        bytes: USDZ file content
    """
    # Create temporary directory for USD assets
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Decode and process the image
        if image_data.startswith('data:image'):
            image_data = image_data.split(',')[1]
        
        image_bytes = base64.b64decode(image_data)
        
        # Get image dimensions for aspect ratio
        with Image.open(BytesIO(image_bytes)) as img:
            img_width, img_height = img.size
            image_aspect_ratio = img_width / img_height
        
        # Set dimensions (60" width, height based on aspect ratio)
        card_width = 1.524  # 60 inches in meters
        card_height = card_width / image_aspect_ratio
        depth = depth_meters
        
        # Frame dimensions
        frame_width = 0.015  # 1.5cm frame width
        recess_depth = 0.002  # 2mm recess
        lip_size = 0.003  # 3mm lip
        # tilt_angle = math.radians(5)  # 5 degrees forward tilt - REMOVED
        
        # Calculate panel dimensions
        front_width = card_width
        front_height = card_height
        back_width = card_width  # Back panel should be same size as front
        back_height = card_height
        
        # Convert to inches for display
        width_inches = card_width * 39.37
        height_inches = card_height * 39.37
        
        print(f"🎨 Enhanced Python USDZ: Creating 3D frame: {card_width:.3f}m × {card_height:.3f}m × {depth:.3f}m ({width_inches:.1f}\" × {height_inches:.1f}\" × {depth*39.37:.1f}\")", file=sys.stderr)
        print(f"🎨 Enhanced Python USDZ: Features: 5° forward tilt, 2mm recessed artwork, 3mm frame lip, dark brown back", file=sys.stderr)
        
        # Create textures
        # Front texture (artwork)
        front_texture_path = os.path.join(temp_dir, 'front_texture.jpg')
        with open(front_texture_path, 'wb') as f:
            f.write(image_bytes)
        
        # Side texture (sampled from edge)
        side_texture_path = os.path.join(temp_dir, 'side_texture.jpg')
        side_texture_data = create_side_texture_from_edge(image_bytes)
        with open(side_texture_path, 'wb') as f:
            f.write(side_texture_data)
        
        # Back texture (dark brown cardboard)
        back_texture_path = os.path.join(temp_dir, 'back_texture.jpg')
        back_texture_data = create_back_panel_texture()
        with open(back_texture_path, 'wb') as f:
            f.write(back_texture_data)
        
        # Create main USD file with 3D structure
        usd_file_path = os.path.join(temp_dir, "enhanced_frame.usda")
        
        # Create USD content with 3D frame structure
        usd_content = f"""#usda 1.0
(
    defaultPrim = "Root"
    upAxis = "Y"
    metersPerUnit = 1
)

def Xform "Root"
{{
    # Frame without tilt
    def Xform "Frame"
    {{
        
        # Front panel (artwork area, recessed by 3mm)
        def Mesh "FrontPanel"
        {{
            int[] faceVertexCounts = [4]
            int[] faceVertexIndices = [0, 1, 2, 3]
            point3f[] points = [
                ({-front_width/2}, {-front_height/2}, {depth - recess_depth}),
                ({front_width/2}, {-front_height/2}, {depth - recess_depth}),
                ({front_width/2}, {front_height/2}, {depth - recess_depth}),
                ({-front_width/2}, {front_height/2}, {depth - recess_depth})
            ]
            color3f[] primvars:displayColor = [(1, 1, 1)]
            texCoord2f[] primvars:st = [(0, 0), (1, 0), (1, 1), (0, 1)] (
                interpolation = "vertex"
            )
            uniform token subdivisionScheme = "none"
            
            rel material:binding = </Root/Frame/FrontMaterial>
        }}
        
        # Back panel (same size as front, at the back surface)
        def Mesh "BackPanel"
        {{
            int[] faceVertexCounts = [4]
            int[] faceVertexIndices = [0, 1, 2, 3]
            point3f[] points = [
                ({-back_width/2}, {-back_height/2}, 0),
                ({back_width/2}, {-back_height/2}, 0),
                ({back_width/2}, {back_height/2}, 0),
                ({-back_width/2}, {back_height/2}, 0)
            ]
            color3f[] primvars:displayColor = [(1, 1, 1)]
            texCoord2f[] primvars:st = [(0, 0), (1, 0), (1, 1), (0, 1)] (
                interpolation = "vertex"
            )
            uniform token subdivisionScheme = "none"
            
            rel material:binding = </Root/Frame/BackMaterial>
        }}
        
        # Back panel reverse face (double-sided rendering)
        def Mesh "BackPanelReverse"
        {{
            int[] faceVertexCounts = [4]
            int[] faceVertexIndices = [0, 2, 1, 3]
            point3f[] points = [
                ({-back_width/2}, {-back_height/2}, 0),
                ({back_width/2}, {-back_height/2}, 0),
                ({back_width/2}, {back_height/2}, 0),
                ({-back_width/2}, {back_height/2}, 0)
            ]
            color3f[] primvars:displayColor = [(1, 1, 1)]
            texCoord2f[] primvars:st = [(0, 0), (1, 0), (1, 1), (0, 1)] (
                interpolation = "vertex"
            )
            uniform token subdivisionScheme = "none"
            
            rel material:binding = </Root/Frame/BackMaterial>
        }}
        
        # Left side panel
        def Mesh "LeftSide"
        {{
            int[] faceVertexCounts = [4]
            int[] faceVertexIndices = [0, 1, 2, 3]
            point3f[] points = [
                ({-front_width/2}, {-front_height/2}, {depth - recess_depth}),
                ({-front_width/2}, {front_height/2}, {depth - recess_depth}),
                ({-back_width/2}, {back_height/2}, 0),
                ({-back_width/2}, {-back_height/2}, 0)
            ]
            color3f[] primvars:displayColor = [(1, 1, 1)]
            texCoord2f[] primvars:st = [(0, 0), (0, 1), (1, 1), (1, 0)] (
                interpolation = "vertex"
            )
            uniform token subdivisionScheme = "none"
            
            rel material:binding = </Root/Frame/SideMaterial>
        }}
        
        # Right side panel
        def Mesh "RightSide"
        {{
            int[] faceVertexCounts = [4]
            int[] faceVertexIndices = [0, 1, 2, 3]
            point3f[] points = [
                ({front_width/2}, {-front_height/2}, {depth - recess_depth}),
                ({front_width/2}, {front_height/2}, {depth - recess_depth}),
                ({back_width/2}, {back_height/2}, 0),
                ({back_width/2}, {-back_height/2}, 0)
            ]
            color3f[] primvars:displayColor = [(1, 1, 1)]
            texCoord2f[] primvars:st = [(0, 0), (0, 1), (1, 1), (1, 0)] (
                interpolation = "vertex"
            )
            uniform token subdivisionScheme = "none"
            
            rel material:binding = </Root/Frame/SideMaterial>
        }}
        
        # Top side panel
        def Mesh "TopSide"
        {{
            int[] faceVertexCounts = [4]
            int[] faceVertexIndices = [0, 1, 2, 3]
            point3f[] points = [
                ({-front_width/2}, {front_height/2}, {depth - recess_depth}),
                ({front_width/2}, {front_height/2}, {depth - recess_depth}),
                ({back_width/2}, {back_height/2}, 0),
                ({-back_width/2}, {back_height/2}, 0)
            ]
            color3f[] primvars:displayColor = [(1, 1, 1)]
            texCoord2f[] primvars:st = [(0, 0), (1, 0), (1, 1), (0, 1)] (
                interpolation = "vertex"
            )
            uniform token subdivisionScheme = "none"
            
            rel material:binding = </Root/Frame/SideMaterial>
        }}
        
        # Bottom side panel
        def Mesh "BottomSide"
        {{
            int[] faceVertexCounts = [4]
            int[] faceVertexIndices = [0, 1, 2, 3]
            point3f[] points = [
                ({-front_width/2}, {-front_height/2}, {depth - recess_depth}),
                ({front_width/2}, {-front_height/2}, {depth - recess_depth}),
                ({back_width/2}, {-back_height/2}, 0),
                ({-back_width/2}, {-back_height/2}, 0)
            ]
            color3f[] primvars:displayColor = [(1, 1, 1)]
            texCoord2f[] primvars:st = [(0, 0), (1, 0), (1, 1), (0, 1)] (
                interpolation = "vertex"
            )
            uniform token subdivisionScheme = "none"
            
            rel material:binding = </Root/Frame/SideMaterial>
        }}
        
        # Double-sided faces for solid rendering (no transparency)
        # Left side reverse face
        def Mesh "LeftSideReverse"
        {{
            int[] faceVertexCounts = [4]
            int[] faceVertexIndices = [0, 2, 1, 3]
            point3f[] points = [
                ({-front_width/2}, {-front_height/2}, {depth - recess_depth}),
                ({-front_width/2}, {front_height/2}, {depth - recess_depth}),
                ({-back_width/2}, {back_height/2}, 0),
                ({-back_width/2}, {-back_height/2}, 0)
            ]
            color3f[] primvars:displayColor = [(1, 1, 1)]
            texCoord2f[] primvars:st = [(0, 0), (0, 1), (1, 1), (1, 0)] (
                interpolation = "vertex"
            )
            uniform token subdivisionScheme = "none"
            
            rel material:binding = </Root/Frame/SideMaterial>
        }}
        
        # Right side reverse face
        def Mesh "RightSideReverse"
        {{
            int[] faceVertexCounts = [4]
            int[] faceVertexIndices = [0, 2, 1, 3]
            point3f[] points = [
                ({front_width/2}, {-front_height/2}, {depth - recess_depth}),
                ({front_width/2}, {front_height/2}, {depth - recess_depth}),
                ({back_width/2}, {back_height/2}, 0),
                ({back_width/2}, {-back_height/2}, 0)
            ]
            color3f[] primvars:displayColor = [(1, 1, 1)]
            texCoord2f[] primvars:st = [(0, 0), (0, 1), (1, 1), (1, 0)] (
                interpolation = "vertex"
            )
            uniform token subdivisionScheme = "none"
            
            rel material:binding = </Root/Frame/SideMaterial>
        }}
        
        # Top side reverse face
        def Mesh "TopSideReverse"
        {{
            int[] faceVertexCounts = [4]
            int[] faceVertexIndices = [0, 2, 1, 3]
            point3f[] points = [
                ({-front_width/2}, {front_height/2}, {depth - recess_depth}),
                ({front_width/2}, {front_height/2}, {depth - recess_depth}),
                ({back_width/2}, {back_height/2}, 0),
                ({-back_width/2}, {back_height/2}, 0)
            ]
            color3f[] primvars:displayColor = [(1, 1, 1)]
            texCoord2f[] primvars:st = [(0, 0), (1, 0), (1, 1), (0, 1)] (
                interpolation = "vertex"
            )
            uniform token subdivisionScheme = "none"
            
            rel material:binding = </Root/Frame/SideMaterial>
        }}
        
        # Bottom side reverse face
        def Mesh "BottomSideReverse"
        {{
            int[] faceVertexCounts = [4]
            int[] faceVertexIndices = [0, 2, 1, 3]
            point3f[] points = [
                ({-front_width/2}, {-front_height/2}, {depth - recess_depth}),
                ({front_width/2}, {-front_height/2}, {depth - recess_depth}),
                ({back_width/2}, {-back_height/2}, 0),
                ({-back_width/2}, {-back_height/2}, 0)
            ]
            color3f[] primvars:displayColor = [(1, 1, 1)]
            texCoord2f[] primvars:st = [(0, 0), (1, 0), (1, 1), (0, 1)] (
                interpolation = "vertex"
            )
            uniform token subdivisionScheme = "none"
            
            rel material:binding = </Root/Frame/SideMaterial>
        }}
        
        # Materials
        def Material "FrontMaterial"
        {{
            token inputs:frame:stPrimvarName = "st"
            token outputs:surface.connect = </Root/Frame/FrontMaterial/PBRShader.outputs:surface>

            def Shader "PBRShader"
            {{
                uniform token info:id = "UsdPreviewSurface"
                float inputs:roughness = 0.8
                float inputs:metallic = 0
                color3f inputs:diffuseColor.connect = </Root/Frame/FrontMaterial/diffuseTexture.outputs:rgb>
                normal3f inputs:normal = (0, 0, 1)
                token outputs:surface
            }}

            def Shader "diffuseTexture"
            {{
                uniform token info:id = "UsdUVTexture"
                asset inputs:file = @front_texture.jpg@
                float2 inputs:st.connect = </Root/Frame/FrontPanel.primvars:st>
                token inputs:wrapS = "repeat"
                token inputs:wrapT = "repeat"
                float3 outputs:rgb
            }}
        }}
        
        def Material "BackMaterial"
        {{
            token inputs:frame:stPrimvarName = "st"
            token outputs:surface.connect = </Root/Frame/BackMaterial/PBRShader.outputs:surface>

            def Shader "PBRShader"
            {{
                uniform token info:id = "UsdPreviewSurface"
                float inputs:roughness = 1.0
                float inputs:metallic = 0
                color3f inputs:diffuseColor.connect = </Root/Frame/BackMaterial/diffuseTexture.outputs:rgb>
                normal3f inputs:normal = (0, 0, -1)
                token outputs:surface
            }}

            def Shader "diffuseTexture"
            {{
                uniform token info:id = "UsdUVTexture"
                asset inputs:file = @back_texture.jpg@
                float2 inputs:st.connect = </Root/Frame/BackPanel.primvars:st>
                token inputs:wrapS = "repeat"
                token inputs:wrapT = "repeat"
                float3 outputs:rgb
            }}
        }}
        
        def Material "SideMaterial"
        {{
            token inputs:frame:stPrimvarName = "st"
            token outputs:surface.connect = </Root/Frame/SideMaterial/PBRShader.outputs:surface>

            def Shader "PBRShader"
            {{
                uniform token info:id = "UsdPreviewSurface"
                float inputs:roughness = 0.9
                float inputs:metallic = 0
                color3f inputs:diffuseColor.connect = </Root/Frame/SideMaterial/diffuseTexture.outputs:rgb>
                normal3f inputs:normal = (1, 0, 0)
                token outputs:surface
            }}

            def Shader "diffuseTexture"
            {{
                uniform token info:id = "UsdUVTexture"
                asset inputs:file = @side_texture.jpg@
                float2 inputs:st.connect = </Root/Frame/LeftSide.primvars:st>
                token inputs:wrapS = "repeat"
                token inputs:wrapT = "repeat"
                float3 outputs:rgb
            }}
        }}
    }}
}}
"""
        
        # Write the USD file
        with open(usd_file_path, 'w') as f:
            f.write(usd_content)
        
        # Create USDZ package with proper compression for AR Quick Look
        print("🎨 Enhanced Python USDZ: Creating enhanced 3D USDZ archive...", file=sys.stderr)
        usdz_data = BytesIO()
        with zipfile.ZipFile(usdz_data, 'w', compression=zipfile.ZIP_STORED) as usdz:
            # Add the USD file (main file must be first in the archive)
            usdz.write(usd_file_path, arcname=os.path.basename(usd_file_path))
            print(f"🎨 Enhanced Python USDZ: Added USD file to archive", file=sys.stderr)
            
            # Add the texture files
            usdz.write(front_texture_path, arcname='front_texture.jpg')
            usdz.write(side_texture_path, arcname='side_texture.jpg')
            usdz.write(back_texture_path, arcname='back_texture.jpg')
            print(f"🎨 Enhanced Python USDZ: Added all textures to archive", file=sys.stderr)
        
        usdz_bytes = usdz_data.getvalue()
        print(f"🎨 Enhanced Python USDZ: Successfully created enhanced 3D USDZ file, size: {len(usdz_bytes)} bytes", file=sys.stderr)
        return usdz_bytes
    
    except Exception as e:
        print(f"Error creating enhanced USDZ: {e}", file=sys.stderr)
        raise
    
    finally:
        # Clean up temporary files
        shutil.rmtree(temp_dir, ignore_errors=True)

def create_side_texture_from_edge(image_bytes):
    """Create side texture by sampling and stretching the frame edge"""
    # Decode image
    image = Image.open(BytesIO(image_bytes))
    if image.mode != 'RGB':
        image = image.convert('RGB')
    
    # Sample 5px from the edge of the frame
    width, height = image.size
    
    # Create a side texture by sampling the outer edge
    edge_pixels = []
    
    # Sample top and bottom edges (horizontal stretching)
    for x in range(0, width, 5):  # Sample every 5px
        # Top edge
        edge_pixels.append(image.getpixel((x, 0)))
        # Bottom edge  
        edge_pixels.append(image.getpixel((x, height-1)))
    
    # Sample left and right edges (vertical stretching)
    for y in range(0, height, 5):  # Sample every 5px
        # Left edge
        edge_pixels.append(image.getpixel((0, y)))
        # Right edge
        edge_pixels.append(image.getpixel((width-1, y)))
    
    # Create a stretched side texture (256x256 for good quality)
    side_image = Image.new('RGB', (256, 256))
    
    # Fill with sampled edge colors in a stretched pattern
    for y in range(256):
        for x in range(256):
            # Use edge pixels in a repeating pattern
            pixel_idx = (x + y) % len(edge_pixels)
            side_image.putpixel((x, y), edge_pixels[pixel_idx])
    
    # Save as high-quality JPEG
    buffer = BytesIO()
    side_image.save(buffer, format='JPEG', quality=95)
    return buffer.getvalue()

def create_back_panel_texture():
    """Create dark brown cardboard-like back panel texture"""
    # Create a 512x512 dark brown texture
    back_image = Image.new('RGB', (512, 512), color=(101, 67, 33))  # Dark brown
    
    # Add subtle cardboard texture variation
    pixels = back_image.load()
    for y in range(512):
        for x in range(512):
            # Add subtle noise for cardboard effect
            noise = random.randint(-10, 10)
            r, g, b = pixels[x, y]
            r = max(0, min(255, r + noise))
            g = max(0, min(255, g + noise))
            b = max(0, min(255, b + noise))
            pixels[x, y] = (r, g, b)
    
    buffer = BytesIO()
    back_image.save(buffer, format='JPEG', quality=95)
    return buffer.getvalue()

if __name__ == "__main__":
    print("🎨 Enhanced Python USDZ: Script started", file=sys.stderr)
    
    try:
        # Read input from command line arguments or stdin
        if len(sys.argv) > 1:
            print(f"🎨 Enhanced Python USDZ: Reading from argv, length: {len(sys.argv[1])}", file=sys.stderr)
            input_data = json.loads(sys.argv[1])
        else:
            print("🎨 Enhanced Python USDZ: Reading from stdin", file=sys.stderr)
            input_data = json.loads(sys.stdin.read())
        
        # Extract parameters
        image_data = input_data.get('imageData', '')
        
        # Calculate proper aspect ratio from the image
        if image_data:
            # Decode image to get dimensions
            if image_data.startswith('data:image'):
                image_data_clean = image_data.split(',')[1]
            else:
                image_data_clean = image_data
                
            try:
                image_bytes = base64.b64decode(image_data_clean)
                with Image.open(BytesIO(image_bytes)) as img:
                    img_width, img_height = img.size
                    aspect_ratio = img_width / img_height
            except:
                aspect_ratio = 1.0  # fallback to square
        else:
            aspect_ratio = 1.0
        
        # Use real-world dimensions - always 60 inches wide (1.524 meters)
        width = 1.524  # 60 inches in meters
        height = width / aspect_ratio
        depth = float(input_data.get('depth', 0.008))  # 8mm depth
        output_path = input_data.get('outputPath', 'enhanced_model.usdz')
        
        # Generate enhanced USDZ
        usdz_data = create_enhanced_3d_usdz_from_image(image_data, width, height, depth)
        
        # Write to file
        with open(output_path, 'wb') as f:
            f.write(usdz_data)
        
        print(f"Enhanced 3D USDZ model generated successfully: {output_path}")
        print(f"File size: {len(usdz_data)} bytes")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
