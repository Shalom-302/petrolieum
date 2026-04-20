"""
Utilities for image processing in the file storage plugin

This module provides functions for transforming, optimizing, and generating image thumbnails.
"""

import io
import os
import uuid
import logging
from typing import BinaryIO, Dict, List, Optional, Tuple, Union, Any
from PIL import Image, ImageOps, ImageFilter, ImageEnhance

logger = logging.getLogger(__name__)


class ImageProcessor:
    """Utility class for image processing in the file storage plugin"""
    
    @staticmethod
    def generate_thumbnail(
        image_data: BinaryIO,
        size: Union[Tuple[int, int], str] = "sm",
        format: str = None,
        quality: int = 85,
        preserve_aspect_ratio: bool = True
    ) -> Tuple[BinaryIO, Dict[str, Any]]:
        """
        Generate a thumbnail from an image
        
        Args:
            image_data: Image source data (binary file)
            size: Thumbnail size. Can be a tuple (width, height) or a predefined size: 
                  "xs" (100x100), "sm" (200x200), "md" (400x400), "lg" (800x800)
            format: Output format (jpeg, png, webp). If None, uses the same format as the original
            quality: Image quality (1-100), applicable for jpeg and webp
            preserve_aspect_ratio: Preserve the image aspect ratio
        
        Returns:
            Tuple containing:
                - Generated thumbnail data (BytesIO)
                - Dictionary with metadata (width, height, format)
        """
        try:
            # Open the image with PIL
            image = Image.open(image_data)
            
            # Convert the size if a string is provided
            if isinstance(size, str):
                size_map = {
                    "xs": (100, 100),
                    "sm": (200, 200),
                    "md": (400, 400),
                    "lg": (800, 800)
                }
                if size not in size_map:
                    size = "sm"
                thumbnail_size = size_map[size]
            else:
                thumbnail_size = size
            
            # Determine the output format
            if not format:
                format = image.format or "JPEG"
            
            format = format.upper()
            
            # Preserve the aspect ratio if requested
            if preserve_aspect_ratio:
                # Create a copy of the image to avoid modifying the original
                thumbnail = image.copy()
                thumbnail.thumbnail(thumbnail_size)
            else:
                # Resize without preserving the aspect ratio
                thumbnail = image.resize(thumbnail_size, Image.Resampling.LANCZOS)
            
            # Convert to RGB if necessary (for JPEG)
            if format == "JPEG" and thumbnail.mode != "RGB":
                thumbnail = thumbnail.convert("RGB")
            
            # Save the thumbnail in a BytesIO
            output = io.BytesIO()
            
            # Determine the format for save()
            save_format = format
            if format == "JPG":
                save_format = "JPEG"
            
            # Save options according to the format
            save_options = {}
            if format in ["JPEG", "WEBP"]:
                save_options["quality"] = quality
                save_options["optimize"] = True
            elif format == "PNG":
                save_options["optimize"] = True
                
            # Save the thumbnail
            thumbnail.save(output, format=save_format, **save_options)
            
            # Reset the BytesIO pointer
            output.seek(0)
            
            # Metadata of the generated thumbnail
            metadata = {
                "width": thumbnail.width,
                "height": thumbnail.height,
                "format": format.lower(),
                "original_size": (image.width, image.height),
                "size_name": size if isinstance(size, str) else None,
                "file_size": output.getbuffer().nbytes
            }
            
            return output, metadata
            
        except Exception as e:
            logger.error(f"Error during thumbnail generation: {str(e)}")
            raise ValueError(f"Unable to generate thumbnail: {str(e)}")
    
    @staticmethod
    def generate_thumbnails(
        image_data: BinaryIO,
        sizes: List[Union[Tuple[int, int], str]] = ["sm", "md", "lg"],
        format: str = None,
        quality: int = 85
    ) -> Dict[str, Tuple[BinaryIO, Dict[str, Any]]]:
        """
        Generate multiple thumbnails at different sizes
        
        Args:
            image_data: Image source data (binary file)
            sizes: List of sizes to generate
            format: Output format (jpeg, png, webp). If None, uses the same format as the original
            quality: Image quality (1-100), applicable for jpeg and webp
        
        Returns:
            Dictionary with sizes as keys and thumbnails as values (data + metadata)
        """
        # Make a copy of the data for each thumbnail
        results = {}
        for size in sizes:
            # Copy the input data
            input_copy = io.BytesIO(image_data.getvalue())
            
            # Generate the thumbnail
            thumbnail_data, metadata = ImageProcessor.generate_thumbnail(
                input_copy, size, format, quality
            )
            
            # Store the result
            size_key = size if isinstance(size, str) else f"{size[0]}x{size[1]}"
            results[size_key] = (thumbnail_data, metadata)
        
        return results
    
    @staticmethod
    def transform_image(
        image_data: BinaryIO,
        operations: List[Dict[str, Any]],
        output_format: str = "jpeg",
        output_quality: int = 85
    ) -> Tuple[BinaryIO, Dict[str, Any]]:
        """
        Apply a series of transformations to an image
        
        Args:
            image_data: Image source data (binary file)
            operations: List of operations to apply. Each operation is a dict with:
                        - "type": type of operation (resize, crop, rotate, filter, etc.)
                        - other operation-specific parameters
            output_format: Output format (jpeg, png, webp)
            output_quality: Image quality (1-100), applicable for jpeg and webp
        
        Returns:
            Tuple containing:
                - Transformed image data (BytesIO)
                - Dictionary with metadata (width, height, format)
        """
        try:
            # Open the image with PIL
            image = Image.open(image_data)
            
            # Apply each operation in order
            for operation in operations:
                op_type = operation.get("type", "").lower()
                
                if op_type == "resize":
                    width = operation.get("width")
                    height = operation.get("height")
                    preserve_aspect = operation.get("preserve_aspect_ratio", True)
                    
                    if width and height:
                        if preserve_aspect:
                            # Preserve the aspect ratio
                            image.thumbnail((width, height), Image.Resampling.LANCZOS)
                        else:
                            # Resize without preserving the aspect ratio
                            image = image.resize((width, height), Image.Resampling.LANCZOS)
                    elif width:
                        # Calculate the height proportionally
                        ratio = width / image.width
                        height = int(image.height * ratio)
                        image = image.resize((width, height), Image.Resampling.LANCZOS)
                    elif height:
                        # Calculate the width proportionally
                        ratio = height / image.height
                        width = int(image.width * ratio)
                        image = image.resize((width, height), Image.Resampling.LANCZOS)
                
                elif op_type == "crop":
                    left = operation.get("left", 0)
                    top = operation.get("top", 0)
                    right = operation.get("right", image.width)
                    bottom = operation.get("bottom", image.height)
                    
                    image = image.crop((left, top, right, bottom))
                
                elif op_type == "rotate":
                    angle = operation.get("angle", 0)
                    expand = operation.get("expand", False)
                    
                    image = image.rotate(angle, expand=expand)
                
                elif op_type == "flip":
                    direction = operation.get("direction", "horizontal")
                    
                    if direction == "horizontal":
                        image = ImageOps.mirror(image)
                    elif direction == "vertical":
                        image = ImageOps.flip(image)
                
                elif op_type == "filter":
                    filter_type = operation.get("filter", "blur")
                    
                    if filter_type == "blur":
                        radius = operation.get("radius", 2)
                        image = image.filter(ImageFilter.GaussianBlur(radius))
                    elif filter_type == "sharpen":
                        image = image.filter(ImageFilter.SHARPEN)
                    elif filter_type == "contour":
                        image = image.filter(ImageFilter.CONTOUR)
                    elif filter_type == "edge_enhance":
                        image = image.filter(ImageFilter.EDGE_ENHANCE)
                    elif filter_type == "emboss":
                        image = image.filter(ImageFilter.EMBOSS)
                
                elif op_type == "adjust":
                    adjust_type = operation.get("adjust", "brightness")
                    factor = operation.get("factor", 1.0)
                    
                    if adjust_type == "brightness":
                        image = ImageEnhance.Brightness(image).enhance(factor)
                    elif adjust_type == "contrast":
                        image = ImageEnhance.Contrast(image).enhance(factor)
                    elif adjust_type == "color":
                        image = ImageEnhance.Color(image).enhance(factor)
                    elif adjust_type == "sharpness":
                        image = ImageEnhance.Sharpness(image).enhance(factor)
                
                elif op_type == "watermark":
                    watermark_image_path = operation.get("image_path")
                    position = operation.get("position", "center")
                    opacity = operation.get("opacity", 0.5)
                    
                    if watermark_image_path and os.path.exists(watermark_image_path):
                        watermark = Image.open(watermark_image_path).convert("RGBA")
                        
                        # Resize the watermark if necessary
                        max_size = operation.get("max_size")
                        if max_size:
                            watermark.thumbnail(max_size, Image.Resampling.LANCZOS)
                        
                        # Adjust opacity
                        if opacity < 1.0:
                            watermark_data = watermark.getdata()
                            new_data = []
                            for item in watermark_data:
                                # Change only the alpha, keep RGB
                                new_data.append((item[0], item[1], item[2], int(item[3] * opacity)))
                            watermark.putdata(new_data)
                        
                        # Convert the main image to RGBA if necessary
                        if image.mode != "RGBA":
                            image = image.convert("RGBA")
                        
                        # Determine the position
                        if position == "center":
                            paste_x = (image.width - watermark.width) // 2
                            paste_y = (image.height - watermark.height) // 2
                        elif position == "top-left":
                            paste_x, paste_y = 0, 0
                        elif position == "top-right":
                            paste_x, paste_y = image.width - watermark.width, 0
                        elif position == "bottom-left":
                            paste_x, paste_y = 0, image.height - watermark.height
                        elif position == "bottom-right":
                            paste_x, paste_y = image.width - watermark.width, image.height - watermark.height
                        else:
                            # Custom position
                            paste_x = operation.get("x", 0)
                            paste_y = operation.get("y", 0)
                        
                        # Add the watermark
                        image.paste(watermark, (paste_x, paste_y), watermark)
            
            # Convert to RGB if necessary (for JPEG)
            output_format = output_format.upper()
            if output_format == "JPEG" and image.mode != "RGB":
                image = image.convert("RGB")
            
            # Save the image to a BytesIO
            output = io.BytesIO()
            
            # Determine the format for save()
            save_format = output_format
            if output_format == "JPG":
                save_format = "JPEG"
            
            # Save options depending on the format
            save_options = {}
            if output_format in ["JPEG", "WEBP"]:
                save_options["quality"] = output_quality
                save_options["optimize"] = True
            elif output_format == "PNG":
                save_options["optimize"] = True
                
            # Save the image
            image.save(output, format=save_format, **save_options)
            
            # Reset the pointer of BytesIO
            output.seek(0)
            
            # Metadata of the generated image
            metadata = {
                "width": image.width,
                "height": image.height,
                "format": output_format.lower(),
                "file_size": output.getbuffer().nbytes,
                "operations_applied": len(operations)
            }
            
            return output, metadata
            
        except Exception as e:
            logger.error(f"Error during image transformation: {str(e)}")
            raise ValueError(f"Unable to transform image: {str(e)}")
    
    @staticmethod
    def get_image_info(image_data: BinaryIO) -> Dict[str, Any]:
        """
        Get information about an image
        
        Args:
            image_data: Image data (binary file)
        
        Returns:
            Dictionary containing image information (dimensions, format, etc.)
        """
        try:
            # Open the image with PIL
            image = Image.open(image_data)
            
            # Get image information
            info = {
                "width": image.width,
                "height": image.height,
                "format": image.format.lower() if image.format else None,
                "mode": image.mode,
                "is_animated": getattr(image, "is_animated", False),
                "n_frames": getattr(image, "n_frames", 1),
                "exif": image.getexif() if hasattr(image, "getexif") else None,
            }
            
            return info
            
        except Exception as e:
            logger.error(f"Error during image information retrieval: {str(e)}")
            raise ValueError(f"Unable to read image information: {str(e)}")
    
    @staticmethod
    def optimize_image(
        image_data: BinaryIO,
        output_format: str = None,
        quality: int = 85,
        max_size: Optional[Tuple[int, int]] = None
    ) -> Tuple[BinaryIO, Dict[str, Any]]:
        """
        Optimise an image for the web
        
        Args:
            image_data: Image data (binary file)
            output_format: Output format (jpeg, png, webp). If None, uses the same format as the original
            quality: Image quality (1-100), applicable for jpeg and webp
            max_size: Maximum size (width, height) to not exceed
        
        Returns:
            Tuple containing:
                - Optimized image data (BytesIO)
                - Dictionary with metadata (width, height, format)
        """
        try:
            # Open the image with PIL
            image = Image.open(image_data)
            
            # Determine the output format
            if not output_format:
                output_format = image.format or "JPEG"
                
            output_format = output_format.upper()
            
            # Resize if necessary
            if max_size and (image.width > max_size[0] or image.height > max_size[1]):
                image.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Convert to RGB if necessary (for JPEG)
            if output_format == "JPEG" and image.mode != "RGB":
                image = image.convert("RGB")
            
            # Save the image to a BytesIO
            output = io.BytesIO()
            
            # Determine the format for save()
            save_format = output_format
            if output_format == "JPG":
                save_format = "JPEG"
            
            # Save options depending on the format
            save_options = {}
            if output_format in ["JPEG", "WEBP"]:
                save_options["quality"] = quality
                save_options["optimize"] = True
            elif output_format == "PNG":
                save_options["optimize"] = True
                
            # Save the image
            image.save(output, format=save_format, **save_options)
            
            # Reset the pointer of BytesIO
            output.seek(0)
            
            # Metadata of the generated image
            metadata = {
                "width": image.width,
                "height": image.height,
                "format": output_format.lower(),
                "file_size": output.getbuffer().nbytes,
                "original_size": image_data.getbuffer().nbytes if hasattr(image_data, "getbuffer") else None,
                "compression_ratio": (
                    image_data.getbuffer().nbytes / output.getbuffer().nbytes 
                    if hasattr(image_data, "getbuffer") else None
                )
            }
            
            return output, metadata
            
        except Exception as e:
            logger.error(f"Error during image optimization: {str(e)}")
            raise ValueError(f"Unable to optimize image: {str(e)}")
