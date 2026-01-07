"""
ROI Data Cache
Thread-safe storage for computed ROI statistics.
"""
import numpy as np
from silx.gui import qt
import threading


class ROIDataCache:
    """Thread-safe cache for ROI statistics data."""
    
    def __init__(self):
        """Initialize the cache with thread lock."""
        self._lock = threading.RLock()
        
        # Storage structure:
        # {roi_name: {
        #     'roi_ref': ROI object,
        #     'means': np.array of mean values,
        #     'computed_frames': set of frame indices that have been computed,
        #     'total_frames': int total frames in dataset,
        #     'color': QColor for display
        # }}
        self._data = {}
    
    def add_roi(self, roi_name, roi_ref, total_frames, color=None):
        """
        Add a new ROI to the cache.
        
        Args:
            roi_name: String identifier for the ROI
            roi_ref: Reference to the actual ROI object
            total_frames: Total number of frames in the dataset
            color: QColor for display (optional)
        """
        with self._lock:
            if color is None:
                color = roi_ref.getColor() if hasattr(roi_ref, 'getColor') else qt.QColor(255, 0, 0)
            
            self._data[roi_name] = {
                'roi_ref': roi_ref,
                'means': np.zeros(total_frames, dtype=np.float32),
                'computed_frames': set(),
                'total_frames': total_frames,
                'color': color
            }
    
    def remove_roi(self, roi_name):
        """Remove an ROI from the cache."""
        with self._lock:
            if roi_name in self._data:
                del self._data[roi_name]
    
    def has_roi(self, roi_name):
        """Check if ROI exists in cache."""
        with self._lock:
            return roi_name in self._data
    
    def set_mean(self, roi_name, frame_index, mean_value):
        """
        Set the mean value for a specific frame.
        
        Args:
            roi_name: String identifier for the ROI
            frame_index: Frame number (0-based)
            mean_value: Mean intensity value
        """
        with self._lock:
            if roi_name not in self._data:
                return
            
            data = self._data[roi_name]
            
            # Resize array if needed
            if frame_index >= len(data['means']):
                new_size = max(frame_index + 1, data['total_frames'])
                old_means = data['means']
                data['means'] = np.zeros(new_size, dtype=np.float32)
                data['means'][:len(old_means)] = old_means
                data['total_frames'] = new_size
            
            data['means'][frame_index] = mean_value
            data['computed_frames'].add(frame_index)
    
    def get_mean(self, roi_name, frame_index):
        """
        Get the mean value for a specific frame.
        
        Returns:
            float or None if not computed yet
        """
        with self._lock:
            if roi_name not in self._data:
                return None
            
            data = self._data[roi_name]
            
            if frame_index not in data['computed_frames']:
                return None
            
            if frame_index >= len(data['means']):
                return None
            
            return float(data['means'][frame_index])
    
    def get_all_means(self, roi_name):
        """
        Get all computed mean values for an ROI.
        
        Returns:
            tuple: (frame_indices, mean_values) as numpy arrays
        """
        with self._lock:
            if roi_name not in self._data:
                return np.array([]), np.array([])
            
            data = self._data[roi_name]
            
            if len(data['computed_frames']) == 0:
                return np.array([]), np.array([])
            
            # Get sorted frame indices
            frames = np.array(sorted(data['computed_frames']), dtype=np.int32)
            means = data['means'][frames]
            
            return frames, means
    
    def get_roi_ref(self, roi_name):
        """Get the ROI object reference."""
        with self._lock:
            if roi_name not in self._data:
                return None
            return self._data[roi_name]['roi_ref']
    
    def get_color(self, roi_name):
        """Get the ROI color."""
        with self._lock:
            if roi_name not in self._data:
                return qt.QColor(255, 255, 255)
            return self._data[roi_name]['color']
    
    def active_rois(self):
        """Get list of active ROI names."""
        with self._lock:
            return list(self._data.keys())
    
    def get_progress(self, roi_name):
        """
        Get computation progress for an ROI.
        
        Returns:
            tuple: (computed_frames, total_frames)
        """
        with self._lock:
            if roi_name not in self._data:
                return 0, 0
            
            data = self._data[roi_name]
            return len(data['computed_frames']), data['total_frames']
    
    def is_fully_computed(self, roi_name):
        """Check if all frames have been computed for this ROI."""
        with self._lock:
            if roi_name not in self._data:
                return False
            
            data = self._data[roi_name]
            return len(data['computed_frames']) >= data['total_frames']
    
    def clear_all(self):
        """Clear all cached data."""
        with self._lock:
            self._data.clear()
    
    def resize_dataset(self, new_total_frames):
        """
        Resize all ROI data arrays for a new dataset size.
        
        Args:
            new_total_frames: New total number of frames
        """
        with self._lock:
            for roi_name in self._data:
                data = self._data[roi_name]
                
                old_size = len(data['means'])
                
                if new_total_frames > old_size:
                    # Expand array
                    old_means = data['means']
                    data['means'] = np.zeros(new_total_frames, dtype=np.float32)
                    data['means'][:old_size] = old_means
                elif new_total_frames < old_size:
                    # Shrink array
                    data['means'] = data['means'][:new_total_frames]
                    # Remove computed frames that are out of range
                    data['computed_frames'] = {f for f in data['computed_frames'] if f < new_total_frames}
                
                data['total_frames'] = new_total_frames
    
    def update_roi_geometry(self, roi_name):
        """
        Mark all frames as needing recomputation when ROI geometry changes.
        
        Args:
            roi_name: String identifier for the ROI
        """
        with self._lock:
            if roi_name not in self._data:
                return
            
            # Clear computed frames - forces recomputation
            self._data[roi_name]['computed_frames'].clear()
    
    def get_stats_summary(self):
        """
        Get summary statistics for debugging.
        
        Returns:
            dict with cache statistics
        """
        with self._lock:
            summary = {
                'total_rois': len(self._data),
                'rois': {}
            }
            
            for roi_name, data in self._data.items():
                summary['rois'][roi_name] = {
                    'total_frames': data['total_frames'],
                    'computed_frames': len(data['computed_frames']),
                    'progress_percent': (len(data['computed_frames']) / data['total_frames'] * 100) 
                                       if data['total_frames'] > 0 else 0
                }
            
            return summary
