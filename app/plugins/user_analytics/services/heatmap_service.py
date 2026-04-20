"""
Service for generating heatmaps from user interaction data.
"""
import io
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from PIL import Image
from datetime import datetime
import base64
import logging
from typing import List, Dict, Any, Optional
from ..models import AnalyticsUserEvent

logger = logging.getLogger(__name__)

class HeatmapService:
    """Service for generating heatmaps from analytics data"""
    
    def generate_heatmap(self, events: List[AnalyticsUserEvent], width: int = 1000, height: int = 800, 
                         radius: int = 30) -> Optional[Dict[str, Any]]:
        """
        Generates a heatmap image from user events
        
        Args:
            events: List of user events with position data
            width: Width of the heatmap in pixels
            height: Height of the heatmap in pixels
            radius: Radius of influence for each event point
            
        Returns:
            Dictionary with heatmap data and metadata or None if generation fails
        """
        if not events:
            logger.warning("No events provided to generate heatmap")
            return None
        
        try:
            # Create an empty density matrix
            heatmap = np.zeros((height, width))
            
            # Fill the matrix with event data
            for event in events:
                # Convert relative positions (0-1) to pixels
                if event.x_position is not None and event.y_position is not None:
                    x = int(event.x_position * width)
                    y = int(event.y_position * height)
                    
                    # Ensure coordinates are within bounds
                    if 0 <= x < width and 0 <= y < height:
                        # Apply a gaussian effect for smoothing
                        for i in range(max(0, y-radius), min(height, y+radius)):
                            for j in range(max(0, x-radius), min(width, x+radius)):
                                # Calculate distance to the central point
                                distance = np.sqrt((i-y)**2 + (j-x)**2)
                                # Apply intensity based on distance (gaussian-like)
                                if distance < radius:
                                    intensity = 1 - (distance/radius)
                                    heatmap[i, j] += intensity
            
            # Normalize values if necessary
            if np.max(heatmap) > 0:
                heatmap = heatmap / np.max(heatmap)
            
            # Create a custom color palette (blue -> green -> yellow -> red)
            colors = [(0,0,0,0), (0,0,1,0.5), (0,1,0,0.7), (1,1,0,0.9), (1,0,0,1)]
            cmap = LinearSegmentedColormap.from_list("heatmap_cmap", colors)
            
            # Create the image with matplotlib
            plt.figure(figsize=(width/100, height/100), dpi=100)
            plt.imshow(heatmap, cmap=cmap)
            plt.axis('off')
            
            # Export as PNG with transparency
            buf = io.BytesIO()
            plt.savefig(buf, format='png', transparent=True, bbox_inches='tight', pad_inches=0)
            plt.close()
            buf.seek(0)
            
            # Convert to base64 for web display
            heatmap_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
            
            return {
                "base64_image": heatmap_base64,
                "width": width,
                "height": height,
                "event_count": len(events),
                "generated_at": datetime.now().isoformat(),
                "data_points": self._get_heatmap_datapoints(events, width, height)
            }
        except Exception as e:
            logger.error(f"Error generating heatmap: {str(e)}")
            return None
    
    def generate_component_heatmap(self, events: List[AnalyticsUserEvent], component_name: str) -> Optional[Dict[str, Any]]:
        """
        Generates a heatmap specific to a UI component
        
        Args:
            events: List of user events
            component_name: Name of the component to analyze
            
        Returns:
            Dictionary with heatmap data or None if generation fails
        """
        # Filter to keep only events from the specified component
        component_events = [e for e in events if e.component_name == component_name]
        
        if not component_events:
            logger.warning(f"No events found for component: {component_name}")
            return None
            
        # Determine average dimensions of the component
        screen_widths = [e.screen_width for e in component_events if e.screen_width]
        screen_heights = [e.screen_height for e in component_events if e.screen_height]
        
        avg_width = int(sum(screen_widths) / len(screen_widths)) if screen_widths else 1000
        avg_height = int(sum(screen_heights) / len(screen_heights)) if screen_heights else 800
        
        # Generate the heatmap with appropriate dimensions
        heatmap_data = self.generate_heatmap(component_events, avg_width, avg_height)
        if heatmap_data:
            heatmap_data["component_name"] = component_name
            
        return heatmap_data
        
    def _get_heatmap_datapoints(self, events: List[AnalyticsUserEvent], width: int, height: int) -> List[Dict[str, Any]]:
        """
        Extracts datapoints for interactive heatmap visualization
        
        Args:
            events: List of user events
            width: Width of the heatmap
            height: Height of the heatmap
            
        Returns:
            List of datapoints with coordinates and metadata
        """
        datapoints = []
        
        for event in events:
            if event.x_position is not None and event.y_position is not None:
                # Convert relative positions to pixels
                x = int(event.x_position * width)
                y = int(event.y_position * height)
                
                if 0 <= x < width and 0 <= y < height:
                    datapoints.append({
                        "x": x,
                        "y": y,
                        "event_type": event.event_type,
                        "target_type": event.target_type,
                        "timestamp": event.timestamp.isoformat() if event.timestamp else None
                    })
        
        return datapoints
