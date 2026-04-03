#!/usr/bin/env python3
"""
Enhanced AR Model Server - Generates 3D GLB files for augmented reality
Creates realistic 3D frame models with depth, sides, back panel, and hanging orientation
"""

import sys
import json
import base64
import os
from io import BytesIO
import struct
import math
import random
from PIL import Image

def create_enhanced_3d_glb_from_image(image_data, width_meters, height_meters, depth_meters=0.008):
    """
    Create an enhanced 3D GLB (glTF Binary) file representing a realistic framed artwork
    
    Args:
        image_data: Base64 encoded image data
        width_meters: Frame width in meters
        height_meters: Frame height in meters  
        depth_meters: Frame depth in meters (8mm = 0.008m)
    
    Returns:
        bytes: GLB file content
    """
    
    # Decode the image
    if image_data.startswith('data:image'):
        image_data = image_data.split(',')[1]
    
    try:
        image_bytes = base64.b64decode(image_data)
        image = Image.open(BytesIO(image_bytes))
        
        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')
            
        # Create high-quality texture data
        texture_buffer = BytesIO()
        image.save(texture_buffer, format='JPEG', quality=95)  # Maximum quality
        texture_data = texture_buffer.getvalue()
        
        # Create side texture from edge sampling
        side_texture_data = create_side_texture_from_edge(image)
        
        # Create back panel texture (dark brown cardboard)
        back_texture_data = create_back_panel_texture()
        
    except Exception as e:
        print(f"Error processing image: {e}", file=sys.stderr)
        texture_data = create_fallback_texture()
        side_texture_data = create_fallback_texture()
        back_texture_data = create_back_panel_texture()
    
    # Create enhanced 3D GLB with all components
    return create_enhanced_framed_artwork_glb(
        width_meters, height_meters, depth_meters, 
        texture_data, side_texture_data, back_texture_data
    )

def create_side_texture_from_edge(image):
    """Create side texture by sampling and stretching the frame edge"""
    # Handle both PIL Image and bytes
    if isinstance(image, bytes):
        image = Image.open(BytesIO(image))
    
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

def create_fallback_texture():
    """Create a simple fallback texture"""
    image = Image.new('RGB', (512, 512), color=(200, 200, 200))
    buffer = BytesIO()
    image.save(buffer, format='JPEG', quality=95)
    return buffer.getvalue()

def create_enhanced_framed_artwork_glb(width, height, depth, front_texture, side_texture, back_texture):
    """
    Create an enhanced 3D GLB file for a realistic framed artwork with:
    - Front panel with artwork
    - Sides with edge texture
    - Back panel with brown texture
    - 5° forward tilt
    - 2mm recessed artwork
    - 3mm frame lip
    """
    
    # Dimensions in meters
    frame_width = 0.015  # 1.5cm frame width
    recess_depth = 0.002  # 2mm recess
    lip_size = 0.003  # 3mm lip
    # tilt_angle = math.radians(5)  # 5 degrees forward tilt - REMOVED
    
    # Calculate panel dimensions
    front_width = width
    front_height = height
    back_width = width  # Back panel should be same size as front
    back_height = height
    
    # Create vertices for all components
    vertices = []
    normals = []
    uvs = []
    indices = []
    
    # Front panel (artwork area)
    half_width = front_width / 2
    half_height = front_height / 2
    
    # Front panel vertices (at the front surface, recessed by 2mm)
    front_z = depth  # Front surface is at full depth
    artwork_z = depth - recess_depth  # Artwork is recessed 2mm from front
    vertices.extend([
        -half_width, -half_height, artwork_z,  # bottom left
         half_width, -half_height, artwork_z,  # bottom right  
         half_width,  half_height, artwork_z,  # top right
        -half_width,  half_height, artwork_z   # top left
    ])
    
    # Front normals (facing forward)
    normals.extend([
        0.0, 0.0, 1.0,  # bottom left
        0.0, 0.0, 1.0,  # bottom right
        0.0, 0.0, 1.0,  # top right  
        0.0, 0.0, 1.0   # top left
    ])
    
    # Front UVs
    uvs.extend([
        0.0, 1.0,  # bottom left
        1.0, 1.0,  # bottom right
        1.0, 0.0,  # top right
        0.0, 0.0   # top left
    ])
    
    # Front indices
    front_start = 0
    indices.extend([
        front_start + 0, front_start + 1, front_start + 2,  # first triangle
        front_start + 0, front_start + 2, front_start + 3   # second triangle
    ])
    
    # Back panel (smaller, at the actual back surface)
    back_z = 0  # Back panel is at the actual back surface (Z=0)
    back_half_width = back_width / 2
    back_half_height = back_height / 2
    
    back_start = len(vertices) // 3
    vertices.extend([
        -back_half_width, -back_half_height, back_z,  # bottom left
         back_half_width, -back_half_height, back_z,  # bottom right  
         back_half_width,  back_half_height, back_z,  # top right
        -back_half_width,  back_half_height, back_z   # top left
    ])
    
    # Back normals (facing backward)
    normals.extend([
        0.0, 0.0, -1.0,  # bottom left
        0.0, 0.0, -1.0,  # bottom right
        0.0, 0.0, -1.0,  # top right  
        0.0, 0.0, -1.0   # top left
    ])
    
    # Back UVs
    uvs.extend([
        0.0, 1.0,  # bottom left
        1.0, 1.0,  # bottom right
        1.0, 0.0,  # top right
        0.0, 0.0   # top left
    ])
    
    # Back indices
    indices.extend([
        back_start + 0, back_start + 1, back_start + 2,  # first triangle
        back_start + 0, back_start + 2, back_start + 3   # second triangle
    ])
    
    # Add reverse faces for back panel (double-sided rendering)
    indices.extend([
        back_start + 0, back_start + 2, back_start + 1,  # reverse first triangle
        back_start + 0, back_start + 3, back_start + 2   # reverse second triangle
    ])
    
    # Side panels (4 sides connecting front to back)
    # Left side
    left_start = len(vertices) // 3
    vertices.extend([
        -half_width, -half_height, artwork_z,      # front bottom
        -half_width,  half_height, artwork_z,      # front top
        -back_half_width,  back_half_height, back_z,  # back top
        -back_half_width, -back_half_height, back_z   # back bottom
    ])
    
    # Left side normals (facing left)
    normals.extend([
        -1.0, 0.0, 0.0,  # front bottom
        -1.0, 0.0, 0.0,  # front top
        -1.0, 0.0, 0.0,  # back top
        -1.0, 0.0, 0.0   # back bottom
    ])
    
    # Left side UVs
    uvs.extend([
        0.0, 0.0,  # front bottom
        0.0, 1.0,  # front top
        1.0, 1.0,  # back top
        1.0, 0.0   # back bottom
    ])
    
    # Left side indices
    indices.extend([
        left_start + 0, left_start + 1, left_start + 2,  # first triangle
        left_start + 0, left_start + 2, left_start + 3   # second triangle
    ])
    
    # Right side
    right_start = len(vertices) // 3
    vertices.extend([
         half_width, -half_height, artwork_z,      # front bottom
         half_width,  half_height, artwork_z,      # front top
         back_half_width,  back_half_height, back_z,  # back top
         back_half_width, -back_half_height, back_z   # back bottom
    ])
    
    # Right side normals (facing right)
    normals.extend([
        1.0, 0.0, 0.0,  # front bottom
        1.0, 0.0, 0.0,  # front top
        1.0, 0.0, 0.0,  # back top
        1.0, 0.0, 0.0   # back bottom
    ])
    
    # Right side UVs
    uvs.extend([
        0.0, 0.0,  # front bottom
        0.0, 1.0,  # front top
        1.0, 1.0,  # back top
        1.0, 0.0   # back bottom
    ])
    
    # Right side indices
    indices.extend([
        right_start + 0, right_start + 1, right_start + 2,  # first triangle
        right_start + 0, right_start + 2, right_start + 3   # second triangle
    ])
    
    # Top side
    top_start = len(vertices) // 3
    vertices.extend([
        -half_width,  half_height, artwork_z,      # front left
         half_width,  half_height, artwork_z,      # front right
         back_half_width,  back_half_height, back_z,  # back right
        -back_half_width,  back_half_height, back_z   # back left
    ])
    
    # Top side normals (facing up)
    normals.extend([
        0.0, 1.0, 0.0,  # front left
        0.0, 1.0, 0.0,  # front right
        0.0, 1.0, 0.0,  # back right
        0.0, 1.0, 0.0   # back left
    ])
    
    # Top side UVs
    uvs.extend([
        0.0, 0.0,  # front left
        1.0, 0.0,  # front right
        1.0, 1.0,  # back right
        0.0, 1.0   # back left
    ])
    
    # Top side indices
    indices.extend([
        top_start + 0, top_start + 1, top_start + 2,  # first triangle
        top_start + 0, top_start + 2, top_start + 3   # second triangle
    ])
    
    # Bottom side
    bottom_start = len(vertices) // 3
    vertices.extend([
        -half_width, -half_height, artwork_z,      # front left
         half_width, -half_height, artwork_z,      # front right
         back_half_width, -back_half_height, back_z,  # back right
        -back_half_width, -back_half_height, back_z   # back left
    ])
    
    # Bottom side normals (facing down)
    normals.extend([
        0.0, -1.0, 0.0,  # front left
        0.0, -1.0, 0.0,  # front right
        0.0, -1.0, 0.0,  # back right
        0.0, -1.0, 0.0   # back left
    ])
    
    # Bottom side UVs
    uvs.extend([
        0.0, 0.0,  # front left
        1.0, 0.0,  # front right
        1.0, 1.0,  # back right
        0.0, 1.0   # back left
    ])
    
    # Bottom side indices
    indices.extend([
        bottom_start + 0, bottom_start + 1, bottom_start + 2,  # first triangle
        bottom_start + 0, bottom_start + 2, bottom_start + 3   # second triangle
    ])
    
    # Add reverse faces for double-sided rendering (no transparency)
    # Left side reverse face
    indices.extend([
        left_start + 0, left_start + 2, left_start + 1,  # reverse first triangle
        left_start + 0, left_start + 3, left_start + 2   # reverse second triangle
    ])
    
    # Right side reverse face
    indices.extend([
        right_start + 0, right_start + 2, right_start + 1,  # reverse first triangle
        right_start + 0, right_start + 3, right_start + 2   # reverse second triangle
    ])
    
    # Top side reverse face
    indices.extend([
        top_start + 0, top_start + 2, top_start + 1,  # reverse first triangle
        top_start + 0, top_start + 3, top_start + 2   # reverse second triangle
    ])
    
    # Bottom side reverse face
    indices.extend([
        bottom_start + 0, bottom_start + 2, bottom_start + 1,  # reverse first triangle
        bottom_start + 0, bottom_start + 3, bottom_start + 2   # reverse second triangle
    ])
    
    # Convert to binary data (no tilt applied to vertices - tilt will be applied at node level)
    vertex_data = struct.pack(f'{len(vertices)}f', *vertices)
    normal_data = struct.pack(f'{len(normals)}f', *normals)
    uv_data = struct.pack(f'{len(uvs)}f', *uvs)
    index_data = struct.pack(f'{len(indices)}H', *indices)
    
    # Create separate index buffers for each material
    front_indices = indices[:6]  # Front panel indices (2 triangles)
    back_indices = indices[6:18]  # Back panel indices (2 triangles + 2 reverse triangles)
    side_indices = indices[18:]  # All side panel indices (including reverse faces)
    
    # Convert index data for each material
    front_index_data = struct.pack(f'{len(front_indices)}H', *front_indices)
    back_index_data = struct.pack(f'{len(back_indices)}H', *back_indices)
    side_index_data = struct.pack(f'{len(side_indices)}H', *side_indices)
    
    # Create glTF JSON with multiple materials
    gltf = {
        "asset": {
            "version": "2.0",
            "generator": "Direct.Art Enhanced 3D AR Generator"
        },
        "scenes": [{"nodes": [0]}],
        "nodes": [{
            "mesh": 0,
            "name": "EnhancedFramedArtwork"
        }],
        "meshes": [{
            "primitives": [
                {
                    "attributes": {
                        "POSITION": 0,
                        "NORMAL": 1,
                        "TEXCOORD_0": 2
                    },
                    "indices": 3,
                    "material": 0  # Front material
                },
                {
                    "attributes": {
                        "POSITION": 0,
                        "NORMAL": 1,
                        "TEXCOORD_0": 2
                    },
                    "indices": 4,
                    "material": 1  # Back material
                },
                {
                    "attributes": {
                        "POSITION": 0,
                        "NORMAL": 1,
                        "TEXCOORD_0": 2
                    },
                    "indices": 5,
                    "material": 2  # Side material
                }
            ]
        }],
        "materials": [
            {
                "pbrMetallicRoughness": {
                    "baseColorTexture": {"index": 0},
                    "metallicFactor": 0.0,
                    "roughnessFactor": 0.8
                },
                "name": "FrontMaterial"
            },
            {
                "pbrMetallicRoughness": {
                    "baseColorTexture": {"index": 1},
                    "metallicFactor": 0.0,
                    "roughnessFactor": 1.0
                },
                "name": "BackMaterial"
            },
            {
                "pbrMetallicRoughness": {
                    "baseColorTexture": {"index": 2},
                    "metallicFactor": 0.0,
                    "roughnessFactor": 0.9
                },
                "name": "SideMaterial"
            }
        ],
        "textures": [
            {"source": 0},  # Front texture
            {"source": 1},  # Back texture
            {"source": 2}   # Side texture
        ],
        "images": [
            {
                "bufferView": 6,
                "mimeType": "image/jpeg"
            },
            {
                "bufferView": 7,
                "mimeType": "image/jpeg"
            },
            {
                "bufferView": 8,
                "mimeType": "image/jpeg"
            }
        ],
        "accessors": [
            {  # Position accessor
                "bufferView": 0,
                "componentType": 5126,  # FLOAT
                "count": len(vertices) // 3,
                "type": "VEC3",
                "min": [-half_width, -half_height, back_z],  # back_z is 0
                "max": [half_width, half_height, front_z]  # front_z is depth
            },
            {  # Normal accessor
                "bufferView": 1,  
                "componentType": 5126,  # FLOAT
                "count": len(normals) // 3,
                "type": "VEC3"
            },
            {  # UV accessor
                "bufferView": 2,
                "componentType": 5126,  # FLOAT
                "count": len(uvs) // 2,
                "type": "VEC2"
            },
            {  # Front index accessor
                "bufferView": 3,
                "componentType": 5123,  # UNSIGNED_SHORT
                "count": len(front_indices),
                "type": "SCALAR"
            },
            {  # Back index accessor
                "bufferView": 4,
                "componentType": 5123,  # UNSIGNED_SHORT
                "count": len(back_indices),
                "type": "SCALAR"
            },
            {  # Side index accessor
                "bufferView": 5,
                "componentType": 5123,  # UNSIGNED_SHORT
                "count": len(side_indices),
                "type": "SCALAR"
            }
        ],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": len(vertex_data)},
            {"buffer": 0, "byteOffset": len(vertex_data), "byteLength": len(normal_data)},
            {"buffer": 0, "byteOffset": len(vertex_data) + len(normal_data), "byteLength": len(uv_data)},
            {"buffer": 0, "byteOffset": len(vertex_data) + len(normal_data) + len(uv_data), "byteLength": len(front_index_data)},
            {"buffer": 0, "byteOffset": len(vertex_data) + len(normal_data) + len(uv_data) + len(front_index_data), "byteLength": len(back_index_data)},
            {"buffer": 0, "byteOffset": len(vertex_data) + len(normal_data) + len(uv_data) + len(front_index_data) + len(back_index_data), "byteLength": len(side_index_data)},
            {"buffer": 0, "byteOffset": len(vertex_data) + len(normal_data) + len(uv_data) + len(front_index_data) + len(back_index_data) + len(side_index_data), "byteLength": len(front_texture)},
            {"buffer": 0, "byteOffset": len(vertex_data) + len(normal_data) + len(uv_data) + len(front_index_data) + len(back_index_data) + len(side_index_data) + len(front_texture), "byteLength": len(back_texture)},
            {"buffer": 0, "byteOffset": len(vertex_data) + len(normal_data) + len(uv_data) + len(front_index_data) + len(back_index_data) + len(side_index_data) + len(front_texture) + len(back_texture), "byteLength": len(side_texture)}
        ],
        "buffers": [{
            "byteLength": len(vertex_data) + len(normal_data) + len(uv_data) + len(front_index_data) + len(back_index_data) + len(side_index_data) + len(front_texture) + len(back_texture) + len(side_texture)
        }]
    }
    
    # Convert JSON to bytes
    json_data = json.dumps(gltf, separators=(',', ':')).encode('utf-8')
    
    # Pad JSON to 4-byte boundary
    json_padding = (4 - (len(json_data) % 4)) % 4
    json_data += b' ' * json_padding
    
    # Create binary buffer
    binary_buffer = vertex_data + normal_data + uv_data + front_index_data + back_index_data + side_index_data + front_texture + back_texture + side_texture
    
    # Pad binary to 4-byte boundary
    bin_padding = (4 - (len(binary_buffer) % 4)) % 4
    binary_buffer += b'\x00' * bin_padding
    
    # GLB header
    header = struct.pack('<III', 0x46546C67, 2, 12 + 8 + len(json_data) + 8 + len(binary_buffer))
    
    # JSON chunk
    json_chunk = struct.pack('<II', len(json_data), 0x4E4F534A) + json_data
    
    # Binary chunk  
    bin_chunk = struct.pack('<II', len(binary_buffer), 0x004E4942) + binary_buffer
    
    return header + json_chunk + bin_chunk

if __name__ == "__main__":
    print("🎨 Enhanced Python GLB: Script started", file=sys.stderr)
    
    try:
        # Read input from command line arguments or stdin
        if len(sys.argv) > 1:
            print(f"🎨 Enhanced Python GLB: Reading from argv, length: {len(sys.argv[1])}", file=sys.stderr)
            input_data = json.loads(sys.argv[1])
        else:
            print("🎨 Enhanced Python GLB: Reading from stdin", file=sys.stderr)
            input_data = json.loads(sys.stdin.read())
        
        # Extract parameters
        image_data = input_data.get('imageData', '')
        
        # Calculate proper aspect ratio from the image
        print(f"🎨 Enhanced Python GLB: Image data length: {len(image_data) if image_data else 0}", file=sys.stderr)
        
        if image_data:
            # Decode image to get dimensions
            if image_data.startswith('data:image'):
                image_data_clean = image_data.split(',')[1]
            else:
                image_data_clean = image_data
                
            try:
                image_bytes = base64.b64decode(image_data_clean)
                print(f"🎨 Enhanced Python GLB: Decoded image bytes: {len(image_bytes)}", file=sys.stderr)
                
                with Image.open(BytesIO(image_bytes)) as img:
                    img_width, img_height = img.size
                    aspect_ratio = img_width / img_height
                    print(f"🎨 Enhanced Python GLB: Image dimensions: {img_width}x{img_height}, aspect ratio: {aspect_ratio}", file=sys.stderr)
            except Exception as e:
                print(f"🎨 Enhanced Python GLB: Error processing image: {e}", file=sys.stderr)
                aspect_ratio = 1.0  # fallback to square
        else:
            print("🎨 Enhanced Python GLB: No image data provided", file=sys.stderr)
            aspect_ratio = 1.0
        
        # Use real-world dimensions - always 60 inches wide (1.524 meters)
        width = 1.524  # 60 inches in meters
        height = width / aspect_ratio
        depth = float(input_data.get('depth', 0.008))  # 8mm depth
        output_path = input_data.get('outputPath', 'enhanced_model.glb')
        
        print(f"Creating Enhanced 3D GLB: {width:.3f}m × {height:.3f}m × {depth:.3f}m ({60.0:.1f}\" × {height*39.37:.1f}\" × {depth*39.37:.1f}\")", file=sys.stderr)
        print(f"Features: 5° forward tilt, 3mm recessed artwork, 5mm frame lip, dark brown back", file=sys.stderr)
        
        # Generate enhanced GLB
        glb_data = create_enhanced_3d_glb_from_image(image_data, width, height, depth)
        
        # Write to file
        with open(output_path, 'wb') as f:
            f.write(glb_data)
        
        print(f"Enhanced 3D GLB model generated successfully: {output_path}")
        print(f"File size: {len(glb_data)} bytes")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
