"""
ROI Data Cache
Thread-safe storage for computed ROI statistics.
"""
import numpy as np
from silx.gui import qt
import threading
import datetime
import os


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
        
        # Live capture mode storage (separate from dataset mode)
        # Stores timeseries data captured during real-time camera preview
        self._live_data = {}
        self._live_frame_counter = 0
        self._live_mode_active = False
        self._live_start_time = None
    
    def set_live_mode(self, active):
        """
        Enable or disable live capture mode.
        
        Args:
            active: True to enable live mode, False to disable
        """
        with self._lock:
            if active and not self._live_mode_active:
                # Starting live mode - reset counters
                self._live_frame_counter = 0
                self._live_start_time = datetime.datetime.now()
            self._live_mode_active = active
    
    def is_live_mode(self):
        """Check if live mode is active."""
        with self._lock:
            return self._live_mode_active
    
    def has_live_data(self):
        """Check if there is any live capture data to save."""
        with self._lock:
            for roi_name in self._live_data:
                if len(self._live_data[roi_name]['means']) > 0:
                    return True
            return False
    
    def get_live_frame_count(self):
        """Get the number of frames captured in live mode."""
        with self._lock:
            return self._live_frame_counter
    
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
            
            # Also initialize live data storage for this ROI
            self._live_data[roi_name] = {
                'means': [],  # Dynamic list for live mode
                'timestamps': [],  # Store timestamps for each frame
                'color': color
            }
    
    def remove_roi(self, roi_name):
        """Remove an ROI from the cache."""
        with self._lock:
            if roi_name in self._data:
                del self._data[roi_name]
            if roi_name in self._live_data:
                del self._live_data[roi_name]
    
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
    
    def append_live_mean(self, roi_name, mean_value, timestamp=None):
        """
        Append a mean value for live capture mode (auto-incrementing frame counter).
        
        Args:
            roi_name: String identifier for the ROI
            mean_value: Mean intensity value
            timestamp: Optional timestamp (defaults to current time)
        """
        with self._lock:
            if roi_name not in self._live_data:
                return
            
            if timestamp is None:
                timestamp = datetime.datetime.now()
            
            self._live_data[roi_name]['means'].append(mean_value)
            self._live_data[roi_name]['timestamps'].append(timestamp)
            
            # Update frame counter to max across all ROIs
            current_len = len(self._live_data[roi_name]['means'])
            if current_len > self._live_frame_counter:
                self._live_frame_counter = current_len
    
    def get_live_means(self, roi_name):
        """
        Get all live capture mean values for an ROI.
        
        Returns:
            tuple: (frame_indices, mean_values) as numpy arrays
        """
        with self._lock:
            if roi_name not in self._live_data:
                return np.array([]), np.array([])
            
            means_list = self._live_data[roi_name]['means']
            
            if len(means_list) == 0:
                return np.array([]), np.array([])
            
            frames = np.arange(len(means_list), dtype=np.int32)
            means = np.array(means_list, dtype=np.float32)
            
            return frames, means
    
    def clear_live_data(self):
        """Clear all live capture data but keep ROI registrations."""
        with self._lock:
            for roi_name in self._live_data:
                self._live_data[roi_name]['means'] = []
                self._live_data[roi_name]['timestamps'] = []
            self._live_frame_counter = 0
            self._live_start_time = None
    
    def export_live_data_to_h5(self, file_path, rois=None):
        """
        Export live capture data to HDF5 file with optional ROI data.
        
        This saves the timeseries data for each ROI (mean values over time),
        and optionally the ROI definitions (geometry, name, color), but NOT
        any source image data.
        
        Args:
            file_path: Path to save HDF5 file
            rois: Optional list of ROI objects to save (from ROI manager)
            
        Returns:
            bool: True if successful, False otherwise
        """
        import h5py
        from gui.roidictionary import roi_to_dict
        
        with self._lock:
            try:
                if not self.has_live_data():
                    return False
                
                roi_names = list(self._live_data.keys())
                if len(roi_names) == 0:
                    return False
                
                with h5py.File(file_path, 'w') as f:
                    # Add metadata
                    f.attrs['type'] = 'live_timeseries'
                    f.attrs['created'] = datetime.datetime.now().isoformat()
                    f.attrs['frame_count'] = self._live_frame_counter
                    if self._live_start_time is not None:
                        f.attrs['start_time'] = self._live_start_time.isoformat()
                    
                    # Create timeseries group
                    ts_group = f.create_group('timeseries')
                    
                    # Store each ROI's timeseries data
                    for roi_name in roi_names:
                        roi_group = ts_group.create_group(roi_name)
                        
                        # Store mean values
                        means = self._live_data[roi_name]['means']
                        if len(means) > 0:
                            roi_group.create_dataset('means', data=np.array(means, dtype=np.float32))
                            roi_group.create_dataset('frames', data=np.arange(len(means), dtype=np.int32))
                        
                        # Store timestamps as ISO strings
                        timestamps = self._live_data[roi_name]['timestamps']
                        if len(timestamps) > 0:
                            ts_strings = [ts.isoformat() for ts in timestamps]
                            dt = h5py.special_dtype(vlen=str)
                            roi_group.create_dataset('timestamps', data=ts_strings, dtype=dt)
                        
                        # Store color if available
                        if roi_name in self._live_data:
                            color = self._live_data[roi_name].get('color')
                            if color is not None and hasattr(color, 'name'):
                                roi_group.attrs['color'] = color.name()
                    
                    # Save ROI definitions if provided
                    if rois is not None and len(rois) > 0:
                        rois_group = f.create_group('rois')
                        
                        for i, roi in enumerate(rois):
                            roi_dict = roi_to_dict(roi)
                            roi_name = roi_dict.get('name', f'roi_{i}')
                            
                            # Create group for this ROI
                            roi_subgroup = rois_group.create_group(roi_name)
                            
                            # Store ROI properties
                            for key, value in roi_dict.items():
                                if isinstance(value, np.ndarray):
                                    roi_subgroup.create_dataset(key, data=value)
                                elif isinstance(value, str):
                                    roi_subgroup.attrs[key] = value
                                elif isinstance(value, (int, float)):
                                    roi_subgroup.attrs[key] = value
                    
                    print(f"Saved live timeseries data to {file_path}")
                
                return True
            except Exception as e:
                print(f"Error exporting live data to HDF5: {e}")
                import traceback
                traceback.print_exc()
                return False
                return False
    
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
            # Note: does not clear live data - use clear_live_data() for that
    
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
