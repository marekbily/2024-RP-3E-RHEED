"""
ROI Mask Utilities
Static helper methods for computing mean intensity values for all ROI types.
"""
import numpy as np
from silx.gui.plot.items.roi import (
    PointROI, CrossROI, LineROI, HorizontalLineROI, VerticalLineROI,
    RectangleROI, CircleROI, EllipseROI, PolygonROI, ArcROI
)


class ROIMaskUtils:
    """Static utility class for ROI mean calculations."""
    
    @staticmethod
    def compute_mean_for_roi(roi, frame_data):
        """
        Calculate mean intensity for any ROI type on given frame.
        
        Args:
            roi: A silx ROI object (PointROI, CircleROI, etc.)
            frame_data: 2D numpy array representing the image frame
            
        Returns:
            float: Mean intensity value, or 0.0 if ROI is invalid/empty
        """
        if frame_data is None or frame_data.size == 0:
            return 0.0
        
        try:
            # Point and Cross ROIs - single pixel value
            if isinstance(roi, (PointROI, CrossROI)):
                return ROIMaskUtils._compute_point_mean(roi, frame_data)
            
            # Line ROIs - mean along line path
            elif isinstance(roi, LineROI):
                return ROIMaskUtils._compute_line_mean(roi, frame_data)
            
            # Horizontal/Vertical line ROIs
            elif isinstance(roi, HorizontalLineROI):
                return ROIMaskUtils._compute_horizontal_line_mean(roi, frame_data)
            
            elif isinstance(roi, VerticalLineROI):
                return ROIMaskUtils._compute_vertical_line_mean(roi, frame_data)
            
            # Shape ROIs - use mask-based calculation
            elif isinstance(roi, (RectangleROI, CircleROI, EllipseROI, PolygonROI, ArcROI)):
                return ROIMaskUtils._compute_mask_mean(roi, frame_data)
            
            else:
                print(f"Warning: Unsupported ROI type: {type(roi).__name__}")
                return 0.0
                
        except Exception as e:
            print(f"Error computing mean for ROI {roi.getName()}: {e}")
            return 0.0
    
    @staticmethod
    def _compute_point_mean(roi, frame_data):
        """Compute mean for Point/Cross ROI (single pixel)."""
        pos = roi.getPosition()
        if pos is None:
            return 0.0
        
        x, y = pos
        height, width = frame_data.shape
        
        # Check bounds
        if 0 <= int(y) < height and 0 <= int(x) < width:
            return float(frame_data[int(y), int(x)])
        return 0.0
    
    @staticmethod
    def _compute_line_mean(roi, frame_data):
        """Compute mean along a line ROI using Bresenham algorithm."""
        endpoints = roi.getEndPoints()
        if endpoints is None or len(endpoints) != 2:
            return 0.0
        
        start, end = endpoints
        if start is None or end is None:
            return 0.0
        
        # Get line coordinates using Bresenham
        coords = ROIMaskUtils._bresenham_line(
            int(start[0]), int(start[1]),
            int(end[0]), int(end[1])
        )
        
        if len(coords) == 0:
            return 0.0
        
        height, width = frame_data.shape
        
        # Filter coordinates that are within bounds
        valid_coords = [(x, y) for x, y in coords 
                       if 0 <= y < height and 0 <= x < width]
        
        if len(valid_coords) == 0:
            return 0.0
        
        # Extract values and compute mean
        values = [frame_data[y, x] for x, y in valid_coords]
        return float(np.mean(values))
    
    @staticmethod
    def _compute_horizontal_line_mean(roi, frame_data):
        """Compute mean for horizontal line ROI."""
        position = roi.getPosition()
        if position is None:
            return 0.0
        
        height, width = frame_data.shape
        y = int(position)
        
        # Check bounds
        if 0 <= y < height:
            return float(np.mean(frame_data[y, :]))
        return 0.0
    
    @staticmethod
    def _compute_vertical_line_mean(roi, frame_data):
        """Compute mean for vertical line ROI."""
        position = roi.getPosition()
        if position is None:
            return 0.0
        
        height, width = frame_data.shape
        x = int(position)
        
        # Check bounds
        if 0 <= x < width:
            return float(np.mean(frame_data[:, x]))
        return 0.0
    
    @staticmethod
    def _compute_mask_mean(roi, frame_data):
        """Compute mean for shape ROIs using mask-based approach."""
        height, width = frame_data.shape
        
        # Create coordinate grids
        y_coords, x_coords = np.ogrid[0:height, 0:width]
        
        # Get mask from ROI
        # For shape ROIs, we need to check each point
        mask = np.zeros((height, width), dtype=bool)
        
        if isinstance(roi, RectangleROI):
            mask = ROIMaskUtils._create_rectangle_mask(roi, height, width)
        elif isinstance(roi, CircleROI):
            mask = ROIMaskUtils._create_circle_mask(roi, height, width)
        elif isinstance(roi, EllipseROI):
            mask = ROIMaskUtils._create_ellipse_mask(roi, height, width)
        elif isinstance(roi, PolygonROI):
            mask = ROIMaskUtils._create_polygon_mask(roi, height, width)
        elif isinstance(roi, ArcROI):
            mask = ROIMaskUtils._create_arc_mask(roi, height, width)
        
        # Compute mean over masked region
        if mask.sum() == 0:
            return 0.0
        
        return float(np.mean(frame_data[mask]))
    
    @staticmethod
    def _create_rectangle_mask(roi, height, width):
        """Create binary mask for rectangle ROI."""
        origin = roi.getOrigin()
        size = roi.getSize()
        
        if origin is None or size is None:
            return np.zeros((height, width), dtype=bool)
        
        x0, y0 = origin
        w, h = size
        
        # Create mask
        y_coords, x_coords = np.ogrid[0:height, 0:width]
        mask = ((x_coords >= x0) & (x_coords < x0 + w) &
                (y_coords >= y0) & (y_coords < y0 + h))
        
        return mask
    
    @staticmethod
    def _create_circle_mask(roi, height, width):
        """Create binary mask for circle ROI."""
        center = roi.getCenter()
        radius = roi.getRadius()
        
        if center is None or radius is None or radius <= 0:
            return np.zeros((height, width), dtype=bool)
        
        cx, cy = center
        
        # Create coordinate grids
        y_coords, x_coords = np.ogrid[0:height, 0:width]
        
        # Distance from center
        dist_sq = (x_coords - cx)**2 + (y_coords - cy)**2
        mask = dist_sq <= radius**2
        
        return mask
    
    @staticmethod
    def _create_ellipse_mask(roi, height, width):
        """Create binary mask for ellipse ROI."""
        center = roi.getCenter()
        
        if center is None:
            return np.zeros((height, width), dtype=bool)
        
        # Get ellipse parameters
        try:
            major_radius = roi.getMajorRadius()
            minor_radius = roi.getMinorRadius()
            orientation = roi.getOrientation() if hasattr(roi, 'getOrientation') else 0
        except:
            return np.zeros((height, width), dtype=bool)
        
        if major_radius <= 0 or minor_radius <= 0:
            return np.zeros((height, width), dtype=bool)
        
        cx, cy = center
        
        # Create coordinate grids
        y_coords, x_coords = np.ogrid[0:height, 0:width]
        x_coords = x_coords.astype(float) - cx
        y_coords = y_coords.astype(float) - cy
        
        # Rotate coordinates
        if orientation != 0:
            angle_rad = np.radians(orientation)
            cos_a = np.cos(angle_rad)
            sin_a = np.sin(angle_rad)
            
            x_rot = x_coords * cos_a + y_coords * sin_a
            y_rot = -x_coords * sin_a + y_coords * cos_a
        else:
            x_rot = x_coords
            y_rot = y_coords
        
        # Ellipse equation
        mask = (x_rot**2 / major_radius**2 + y_rot**2 / minor_radius**2) <= 1
        
        return mask
    
    @staticmethod
    def _create_polygon_mask(roi, height, width):
        """Create binary mask for polygon ROI."""
        points = roi.getPoints()
        
        if points is None or len(points) < 3:
            return np.zeros((height, width), dtype=bool)
        
        # Use matplotlib path for point-in-polygon test
        from matplotlib.path import Path
        
        # Create coordinate grids
        y_coords, x_coords = np.meshgrid(np.arange(height), np.arange(width), indexing='ij')
        coords = np.column_stack([x_coords.ravel(), y_coords.ravel()])
        
        # Create path and test
        path = Path(points)
        mask = path.contains_points(coords).reshape(height, width)
        
        return mask
    
    @staticmethod
    def _create_arc_mask(roi, height, width):
        """Create binary mask for arc ROI."""
        # Arc ROI is complex - for now use circle approximation
        # Can be refined if needed
        try:
            center = roi.getCenter()
            inner_radius = roi.getInnerRadius()
            outer_radius = roi.getOuterRadius()
            
            if center is None or inner_radius is None or outer_radius is None:
                return np.zeros((height, width), dtype=bool)
            
            cx, cy = center
            
            # Create coordinate grids
            y_coords, x_coords = np.ogrid[0:height, 0:width]
            
            # Distance from center
            dist_sq = (x_coords - cx)**2 + (y_coords - cy)**2
            mask = (dist_sq >= inner_radius**2) & (dist_sq <= outer_radius**2)
            
            # TODO: Add angle filtering for start/end angles if needed
            
            return mask
        except:
            return np.zeros((height, width), dtype=bool)
    
    @staticmethod
    def _bresenham_line(x0, y0, x1, y1):
        """
        Generate coordinates along a line using Bresenham's algorithm.
        
        Returns:
            list of (x, y) tuples
        """
        coords = []
        
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        
        err = dx - dy
        
        x, y = x0, y0
        
        while True:
            coords.append((x, y))
            
            if x == x1 and y == y1:
                break
            
            e2 = 2 * err
            
            if e2 > -dy:
                err -= dy
                x += sx
            
            if e2 < dx:
                err += dx
                y += sy
        
        return coords
