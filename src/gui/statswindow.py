"""
ROI Statistics Window
Custom implementation with non-blocking computation and timeseries plotting.
"""
from silx.gui import qt
import numpy as np
from silx.gui.plot import Plot1D
from silx.gui.plot.StackView import StackView
from silx.gui.plot.items import Marker
from gui.custom_stats_table import CustomROIStatsTable
from gui.roi_data_cache import ROIDataCache
from gui.roi_computation_engine import ROIComputationEngine
import os


# Time format options
TIME_FORMAT_RELATIVE = 0  # HH:MM:SS from start
TIME_FORMAT_ABSOLUTE = 1  # Actual timestamp
TIME_FORMAT_FRAMES = 2    # Frame numbers only


class RecordingInfoPanel(qt.QWidget):
    """Collapsible panel showing recording metadata."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        layout = qt.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        # Toggle button
        self._toggleButton = qt.QPushButton("▶ Recording Info")
        self._toggleButton.setCheckable(True)
        self._toggleButton.setStyleSheet("QPushButton { text-align: left; padding: 3px; }")
        self._toggleButton.clicked.connect(self._toggle)
        layout.addWidget(self._toggleButton)
        
        # Content widget (hidden by default)
        self._content = qt.QWidget()
        self._content.setVisible(False)
        content_layout = qt.QFormLayout(self._content)
        content_layout.setContentsMargins(10, 5, 5, 5)
        content_layout.setSpacing(3)
        
        # Info labels
        self._startTimeLabel = qt.QLabel("--")
        self._fpsLabel = qt.QLabel("--")
        self._framesLabel = qt.QLabel("--")
        self._durationLabel = qt.QLabel("--")
        self._fileSizeLabel = qt.QLabel("--")
        self._resolutionLabel = qt.QLabel("--")
        
        content_layout.addRow("Start Time:", self._startTimeLabel)
        content_layout.addRow("FPS:", self._fpsLabel)
        content_layout.addRow("Total Frames:", self._framesLabel)
        content_layout.addRow("Duration:", self._durationLabel)
        content_layout.addRow("File Size:", self._fileSizeLabel)
        content_layout.addRow("Resolution:", self._resolutionLabel)
        
        layout.addWidget(self._content)
    
    def _toggle(self):
        """Toggle panel visibility."""
        expanded = self._toggleButton.isChecked()
        self._content.setVisible(expanded)
        self._toggleButton.setText("▼ Recording Info" if expanded else "▶ Recording Info")
    
    def updateInfo(self, start_time=None, fps=None, total_frames=None, 
                   file_path=None, resolution=None):
        """Update the recording information display."""
        # Start time
        if start_time is not None:
            try:
                from datetime import datetime
                if isinstance(start_time, str):
                    dt = datetime.fromisoformat(start_time)
                    self._startTimeLabel.setText(dt.strftime('%Y-%m-%d %H:%M:%S'))
                else:
                    self._startTimeLabel.setText(str(start_time))
            except Exception:
                self._startTimeLabel.setText(str(start_time) if start_time else "--")
        else:
            self._startTimeLabel.setText("--")
        
        # FPS
        if fps is not None:
            self._fpsLabel.setText(f"{fps:.2f}")
        else:
            self._fpsLabel.setText("--")
        
        # Total frames
        if total_frames is not None:
            self._framesLabel.setText(str(total_frames))
        else:
            self._framesLabel.setText("--")
        
        # Duration
        if fps is not None and fps > 0 and total_frames is not None:
            duration_sec = total_frames / fps
            hours = int(duration_sec // 3600)
            minutes = int((duration_sec % 3600) // 60)
            secs = int(duration_sec % 60)
            if hours > 0:
                self._durationLabel.setText(f"{hours:02d}:{minutes:02d}:{secs:02d}")
            else:
                self._durationLabel.setText(f"{minutes:02d}:{secs:02d}")
        else:
            self._durationLabel.setText("--")
        
        # File size
        if file_path is not None and os.path.exists(file_path):
            try:
                size_bytes = os.path.getsize(file_path)
                if size_bytes >= 1024 * 1024 * 1024:
                    self._fileSizeLabel.setText(f"{size_bytes / (1024**3):.2f} GB")
                elif size_bytes >= 1024 * 1024:
                    self._fileSizeLabel.setText(f"{size_bytes / (1024**2):.2f} MB")
                elif size_bytes >= 1024:
                    self._fileSizeLabel.setText(f"{size_bytes / 1024:.2f} KB")
                else:
                    self._fileSizeLabel.setText(f"{size_bytes} bytes")
            except Exception:
                self._fileSizeLabel.setText("--")
        else:
            self._fileSizeLabel.setText("--")
        
        # Resolution
        if resolution is not None:
            self._resolutionLabel.setText(f"{resolution[1]} x {resolution[0]}")
        else:
            self._resolutionLabel.setText("--")
    
    def clear(self):
        """Clear all info."""
        self.updateInfo()


class roiStatsWindow(qt.QWidget):
    """Window that embeds the custom stats table and timeseries plot."""

    def __init__(self, parent=None, plot=None, stackview=None, roimanager=None):
        """
        Create a window with custom stats table and timeseries plotting.
        
        Args:
            parent: Parent widget
            plot: Plot2D instance
            stackview: StackView or Plot2D instance
            roimanager: RegionOfInterestManager instance
        """
        super().__init__(parent)
        
        assert plot is not None
        self._plot2d = plot
        self._view = stackview
        self._roiManager = roimanager
        
        # Initialize data cache and computation engine
        self.data_cache = ROIDataCache()
        self.computation_engine = ROIComputationEngine(self.data_cache)
        
        # Main layout
        layout = qt.QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(5)
        
        # Recording info panel (collapsible)
        self._infoPanel = RecordingInfoPanel(self)
        layout.addWidget(self._infoPanel)
        
        # Create custom stats table
        self.statsTable = CustomROIStatsTable(self._roiManager, parent=self)
        
        # Timeseries plot window (hidden by default)
        self._timeseries = qt.QWidget()
        timeseries_layout = qt.QVBoxLayout()
        self._timeseries.setLayout(timeseries_layout)
        self._timeseries.setWindowTitle("ROI Time Series")
        
        # Time format selector toolbar
        toolbar_layout = qt.QHBoxLayout()
        toolbar_layout.addWidget(qt.QLabel("X-Axis Format:"))
        self._timeFormatCombo = qt.QComboBox()
        self._timeFormatCombo.addItem("Relative Time (HH:MM:SS)", TIME_FORMAT_RELATIVE)
        self._timeFormatCombo.addItem("Absolute Time", TIME_FORMAT_ABSOLUTE)
        self._timeFormatCombo.addItem("Frame Numbers", TIME_FORMAT_FRAMES)
        self._timeFormatCombo.currentIndexChanged.connect(self._on_time_format_changed)
        toolbar_layout.addWidget(self._timeFormatCombo)
        toolbar_layout.addStretch()
        timeseries_layout.addLayout(toolbar_layout)
        
        self._timeseries.plot = Plot1D()
        timeseries_layout.addWidget(self._timeseries.plot)
        self._timeseries.plot.setGraphXLabel("Frame number")
        self._timeseries.plot.setGraphYLabel("Intensity")
        self._timeseries.plot.setGraphTitle("ROI Time Series")
        self._timeseries.plot.setKeepDataAspectRatio(False)
        self._timeseries.plot.setActiveCurveHandling(False)
        self._timeseries.plot.setBackend("opengl")
        self._timeseries.plot.setGraphGrid(False)
        
        # Enable interactive tooltip
        self._timeseries.plot.setInteractiveMode('zoom')
        
        # Connect mouse move signal for hover tooltip
        self._timeseries.plot.sigPlotSignal.connect(self._on_plot_mouse_move)
        
        # Enable legend with colored boxes - access legend widget and show it
        legend_widget = self._timeseries.plot.getLegendsDockWidget()
        if legend_widget is not None:
            legend_widget.show()
        
        # Vertical cursor line marker (for current frame position)
        self._cursorMarker = None
        
        self._timeseries.hide()
        
        # Button layout
        btnLayout = qt.QHBoxLayout()
        btnLayout.setAlignment(qt.Qt.AlignmentFlag.AlignVCenter)
        
        self.timeseriesButton = qt.QPushButton("Show Timeseries Plot", self)
        self.addAllButton = qt.QPushButton("Add All ROIs", self)
        
        btnLayout.addStretch(2)
        btnLayout.addWidget(self.addAllButton)
        btnLayout.addWidget(self.timeseriesButton)
        
        # Add widgets to layout
        layout.addWidget(self.statsTable)
        layout.addLayout(btnLayout)
        
        # Connect signals
        self.statsTable.roiAddRequested.connect(self._on_roi_added)
        self.statsTable.roiRemoveRequested.connect(self._on_roi_removed)
        self.timeseriesButton.clicked.connect(self.showTimeseries)
        self.addAllButton.clicked.connect(self.addAllRois)
        
        # Connect computation engine signals
        self.computation_engine.currentFrameReady.connect(self._on_current_frame_ready)
        self.computation_engine.bulkProgressUpdated.connect(self._on_bulk_progress)
        self.computation_engine.bulkAnalysisComplete.connect(self._on_bulk_complete)
        self.computation_engine.errorOccurred.connect(self._on_computation_error)
        
        # Start computation engine
        self.computation_engine.start()
        
        # Track current dataset info
        self._dataset = None
        self._total_frames = 0
        self._current_frame_index = 0
        
        # Recording metadata for time display
        self._recording_fps = None
        self._recording_start_timestamp = None
        self._current_h5_path = None
        self._frame_resolution = None
        
        # Time format setting (default to relative)
        self._time_format = TIME_FORMAT_RELATIVE
        
        # Track live capture mode
        self._is_live_mode = False
    
    def setLiveMode(self, active):
        """
        Enable or disable live capture mode for real-time stats tracking.
        
        Args:
            active: True to enable live mode, False to disable
        """
        self._is_live_mode = active
        self.data_cache.set_live_mode(active)
        
        if active:
            # Starting live mode
            print("Live capture mode enabled - tracking real-time statistics")
    
    def setRecordingMetadata(self, fps, start_timestamp, file_path=None, resolution=None):
        """
        Set recording metadata for time-based display.
        
        Args:
            fps: Recording FPS (frames per second)
            start_timestamp: ISO format timestamp string of recording start
            file_path: Path to the H5 file (for file size display)
            resolution: Tuple of (height, width) for resolution display
        """
        self._recording_fps = fps
        self._recording_start_timestamp = start_timestamp
        self._current_h5_path = file_path
        self._frame_resolution = resolution
        
        # Update info panel
        self._infoPanel.updateInfo(
            start_time=start_timestamp,
            fps=fps,
            total_frames=self._total_frames,
            file_path=file_path,
            resolution=resolution
        )
        
        # Update timeseries plot
        self._update_axis_label()
    
    def _update_axis_label(self):
        """Update the X-axis label based on current time format setting."""
        time_format = self._timeFormatCombo.currentData()
        
        if time_format == TIME_FORMAT_FRAMES or self._recording_fps is None:
            self._timeseries.plot.setGraphXLabel("Frame")
        else:
            self._timeseries.plot.setGraphXLabel("Seconds")
    
    def _on_time_format_changed(self, index):
        """Handle time format selection change."""
        self._time_format = self._timeFormatCombo.currentData()
        self._update_axis_label()
        self._update_timeseries_plot()
    
    def _format_time_for_frame(self, frame_index, include_frame_num=True):
        """
        Format time string for a given frame index.
        
        Args:
            frame_index: Frame number (0-based)
            include_frame_num: Whether to include frame number in parentheses
            
        Returns:
            str: Formatted time string based on current format setting
        """
        time_format = self._timeFormatCombo.currentData() if hasattr(self, '_timeFormatCombo') else TIME_FORMAT_FRAMES
        
        if time_format == TIME_FORMAT_FRAMES or self._recording_fps is None or self._recording_fps <= 0:
            return str(int(frame_index))
        
        total_seconds = frame_index / self._recording_fps
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        secs = int(total_seconds % 60)
        
        if time_format == TIME_FORMAT_RELATIVE:
            if hours > 0:
                time_str = f"{hours:02d}:{minutes:02d}:{secs:02d}"
            else:
                time_str = f"{minutes:02d}:{secs:02d}"
        elif time_format == TIME_FORMAT_ABSOLUTE:
            # Calculate absolute time from start timestamp
            if self._recording_start_timestamp is not None:
                try:
                    from datetime import datetime, timedelta
                    if isinstance(self._recording_start_timestamp, str):
                        start_dt = datetime.fromisoformat(self._recording_start_timestamp)
                    else:
                        start_dt = self._recording_start_timestamp
                    current_dt = start_dt + timedelta(seconds=total_seconds)
                    time_str = current_dt.strftime('%H:%M:%S')
                except Exception:
                    time_str = f"{hours:02d}:{minutes:02d}:{secs:02d}"
            else:
                time_str = f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            time_str = f"{hours:02d}:{minutes:02d}:{secs:02d}"
        
        if include_frame_num:
            return f"{time_str} ({int(frame_index)})"
        return time_str
    
    def _on_plot_mouse_move(self, event):
        """Handle mouse move events for hover tooltip."""
        if event['event'] != 'mouseMoved':
            return
        
        x, y = event['x'], event['y']
        if x is None or y is None:
            return
        
        # Find closest data point
        closest_roi = None
        closest_frame = None
        closest_mean = None
        min_distance = float('inf')
        
        for roi_name in self.statsTable.get_roi_names():
            if self._is_live_mode:
                frames, means = self.data_cache.get_live_means(roi_name)
            else:
                frames, means = self.data_cache.get_all_means(roi_name)
            
            if len(frames) == 0:
                continue
            
            # Convert to display X values based on format
            if self._recording_fps is not None and self._recording_fps > 0:
                time_format = self._timeFormatCombo.currentData()
                if time_format != TIME_FORMAT_FRAMES:
                    x_values = frames / self._recording_fps
                else:
                    x_values = frames
            else:
                x_values = frames
            
            # Find closest point
            for i, (xv, mv) in enumerate(zip(x_values, means)):
                dist = abs(xv - x)
                if dist < min_distance:
                    min_distance = dist
                    closest_roi = roi_name
                    closest_frame = frames[i]
                    closest_mean = mv
        
        # Show tooltip if close enough
        if closest_roi is not None and min_distance < (self._timeseries.plot.getGraphXLimits()[1] - self._timeseries.plot.getGraphXLimits()[0]) * 0.02:
            time_str = self._format_time_for_frame(closest_frame, include_frame_num=True)
            tooltip = f"{closest_roi}\n{time_str}\nMean: {closest_mean:.2f}"
            qt.QToolTip.showText(qt.QCursor.pos(), tooltip)
        else:
            qt.QToolTip.hideText()
    
    def updateCursorPosition(self, frame_index):
        """
        Update the vertical cursor line position on the timeseries plot.
        
        Args:
            frame_index: Current frame number
        """
        if not self._timeseries.isVisible():
            return
        
        # Calculate X position based on format
        if self._recording_fps is not None and self._recording_fps > 0:
            time_format = self._timeFormatCombo.currentData()
            if time_format != TIME_FORMAT_FRAMES:
                x_pos = frame_index / self._recording_fps
            else:
                x_pos = frame_index
        else:
            x_pos = frame_index
        
        # Remove existing cursor marker
        if self._cursorMarker is not None:
            self._timeseries.plot.remove(legend='_cursor_line')
        
        # Add vertical line at current position
        self._timeseries.plot.addXMarker(x_pos, legend='_cursor_line', 
                                          text=self._format_time_for_frame(frame_index),
                                          color='red')
    
    def promptSaveLiveData(self):
        """
        Prompt user to save live capture data before switching modes.
        
        Returns:
            bool: True if user chose to proceed (save or discard), False if cancelled
        """
        if not self.data_cache.has_live_data():
            return True  # No data to save, proceed
        
        frame_count = self.data_cache.get_live_frame_count()
        roi_count = len(self.statsTable.get_roi_names())
        
        dialog = qt.QMessageBox(self)
        dialog.setWindowTitle("Save Live Capture Data?")
        dialog.setText(f"You have captured {frame_count} frames of real-time statistics data for {roi_count} ROI(s).")
        dialog.setInformativeText("Do you want to save this data before switching modes?")
        
        save_btn = dialog.addButton("Save to HDF5", qt.QMessageBox.AcceptRole)
        discard_btn = dialog.addButton("Discard", qt.QMessageBox.DestructiveRole)
        cancel_btn = dialog.addButton("Cancel", qt.QMessageBox.RejectRole)
        dialog.setDefaultButton(save_btn)
        
        dialog.exec()
        
        clicked = dialog.clickedButton()
        
        if clicked == save_btn:
            # Save to HDF5 file
            return self._save_live_data_dialog()
        elif clicked == discard_btn:
            # Clear live data and proceed
            self.data_cache.clear_live_data()
            return True
        else:
            # Cancel - don't proceed
            return False
    
    def _save_live_data_dialog(self):
        """
        Show file dialog and save live data to HDF5.
        
        Returns:
            bool: True if saved successfully or user chose to skip, False if cancelled
        """
        import datetime
        import os
        
        # Default filename with timestamp
        default_name = f"live_timeseries_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.h5"
        default_path = os.path.join(os.getcwd(), "cacheimg", default_name)
        
        file_path, _ = qt.QFileDialog.getSaveFileName(
            self,
            "Save Live Capture Data",
            default_path,
            "HDF5 Files (*.h5);;All Files (*)"
        )
        
        if not file_path:
            # User cancelled file dialog - ask if they want to discard
            reply = qt.QMessageBox.question(
                self,
                "Discard Data?",
                "No file selected. Do you want to discard the live capture data?",
                qt.QMessageBox.Yes | qt.QMessageBox.No,
                qt.QMessageBox.No
            )
            if reply == qt.QMessageBox.Yes:
                self.data_cache.clear_live_data()
                return True
            return False
        
        # Ensure .h5 extension
        if not file_path.endswith('.h5'):
            file_path += '.h5'
        
        # Collect ROI data if available
        rois_to_save = None
        if self._roiManager is not None:
            # Get all ROIs from the manager
            rois_to_save = list(self._roiManager.getRois())
        
        # Save to HDF5
        success = self.data_cache.export_live_data_to_h5(file_path, rois_to_save)
        
        if success:
            qt.QMessageBox.information(
                self,
                "Data Saved",
                f"Live capture data saved to:\n{file_path}"
            )
            self.data_cache.clear_live_data()
            return True
        else:
            qt.QMessageBox.warning(
                self,
                "Save Failed",
                "Failed to save live capture data. Please try again."
            )
            return False
    
    def setDataset(self, dataset):
        """
        Set the dataset for ROI analysis.
        Prompts to save live data if switching from live mode.
        
        Args:
            dataset: Numpy array or h5py dataset with shape (N, H, W) or (H, W)
        """
        # Check if we're switching from live mode to dataset mode
        if self._is_live_mode and dataset is not None:
            # Prompt user about live data
            if not self.promptSaveLiveData():
                return  # User cancelled, don't switch
            
            # Disable live mode
            self.setLiveMode(False)
        
        self._dataset = dataset
        
        if dataset is not None:
            if dataset.ndim == 3:
                self._total_frames = dataset.shape[0]
                self._frame_resolution = dataset.shape[1:3]  # (height, width)
            elif dataset.ndim == 2:
                self._total_frames = 1
                self._frame_resolution = dataset.shape
            else:
                self._total_frames = 0
                self._frame_resolution = None
        else:
            self._total_frames = 0
            self._frame_resolution = None
        
        # Update info panel with new frame count
        self._infoPanel.updateInfo(
            start_time=self._recording_start_timestamp,
            fps=self._recording_fps,
            total_frames=self._total_frames,
            file_path=self._current_h5_path,
            resolution=self._frame_resolution
        )
        
        # Update computation engine
        self.computation_engine.set_dataset(dataset)
        
        # Resize cache for all existing ROIs
        self.data_cache.resize_dataset(self._total_frames)
        
        # Re-queue bulk analysis for all ROIs
        for roi_name in self.statsTable.get_roi_names():
            roi = self.data_cache.get_roi_ref(roi_name)
            if roi is not None:
                self.computation_engine.queue_bulk_analysis(roi_name, roi, self._total_frames)
    
    def updateCurrentFrame(self, frame_index, frame_data=None):
        """
        Update statistics for the current frame.
        
        Args:
            frame_index: Current frame number (0-based)
            frame_data: Optional 2D frame data (will be extracted from dataset if not provided)
        """
        self._current_frame_index = frame_index
        
        # Get frame data if not provided
        if frame_data is None and self._dataset is not None:
            try:
                if self._dataset.ndim == 3:
                    frame_data = self._dataset[frame_index]
                elif self._dataset.ndim == 2:
                    frame_data = self._dataset
            except Exception as e:
                print(f"Error extracting frame data: {e}")
                return
        
        if frame_data is None:
            return
        
        # Build list of ROIs to compute
        roi_list = []
        for roi_name in self.statsTable.get_roi_names():
            roi = self.data_cache.get_roi_ref(roi_name)
            if roi is not None:
                roi_list.append((roi_name, roi))
        
        if len(roi_list) > 0:
            # Queue priority computation for current frame
            # Pass live_mode flag so engine knows to store in live cache
            self.computation_engine.queue_current_frame(
                frame_index, 
                frame_data, 
                roi_list,
                is_live_mode=self._is_live_mode
            )
    
    def _on_roi_added(self, roi):
        """Handle ROI added to stats table."""
        roi_name = roi.getName()
        color = roi.getColor() if hasattr(roi, 'getColor') else qt.QColor(255, 0, 0)
        
        # Add to cache
        self.data_cache.add_roi(roi_name, roi, self._total_frames, color)
        
        # Queue bulk analysis
        if self._total_frames > 0:
            self.computation_engine.queue_bulk_analysis(roi_name, roi, self._total_frames)
        
        # Compute current frame immediately
        if self._dataset is not None:
            try:
                if self._dataset.ndim == 3:
                    frame_data = self._dataset[self._current_frame_index]
                elif self._dataset.ndim == 2:
                    frame_data = self._dataset
                else:
                    return
                
                self.computation_engine.queue_current_frame(
                    self._current_frame_index, 
                    frame_data, 
                    [(roi_name, roi)]
                )
            except Exception as e:
                print(f"Error computing initial frame for {roi_name}: {e}")
    
    def _on_roi_removed(self, roi_name):
        """Handle ROI removed from stats table."""
        # Remove from cache
        self.data_cache.remove_roi(roi_name)
        
        # Update timeseries plot if open
        if self._timeseries.isVisible():
            self._update_timeseries_plot()
    
    def _on_current_frame_ready(self, roi_name, mean_value):
        """Handle current frame computation result."""
        # Update table display
        self.statsTable.update_mean_value(roi_name, mean_value)
        
        # In live mode, also update timeseries plot in real-time
        if self._is_live_mode and self._timeseries.isVisible():
            self._update_timeseries_plot()
    
    def _on_bulk_progress(self, roi_name, computed_frames, total_frames):
        """Handle bulk computation progress update."""
        # Update progress display
        self.statsTable.update_progress(roi_name, computed_frames, total_frames)
        
        # Update timeseries plot if visible
        if self._timeseries.isVisible():
            self._update_timeseries_plot()
    
    def _on_bulk_complete(self, roi_name):
        """Handle bulk computation completion."""
        # Mark as complete
        self.statsTable.mark_complete(roi_name)
        
        # Update timeseries plot if visible
        if self._timeseries.isVisible():
            self._update_timeseries_plot()
    
    def _on_computation_error(self, roi_name, error_message):
        """Handle computation error."""
        print(f"Computation error for {roi_name}: {error_message}")

    def addAllRois(self):
        """Add all available ROIs to the stats table."""
        if self._roiManager is None:
            qt.QMessageBox.warning(self, "No ROI Manager", 
                                  "ROI manager is not available.")
            return
        
        available_rois = self._roiManager.getRois()
        
        if len(available_rois) == 0:
            qt.QMessageBox.information(self, "No ROIs",
                                      "No ROIs have been created yet.")
            return
        
        # Add each ROI that's not already in the table
        added_count = 0
        for roi in available_rois:
            roi_name = roi.getName()
            if not self.statsTable.has_roi(roi_name):
                # Add to table
                self.statsTable._add_table_row(roi)
                self.statsTable.roi_names_in_table.add(roi_name)
                
                # Trigger computation
                self._on_roi_added(roi)
                added_count += 1
        
        if added_count > 0:
            qt.QMessageBox.information(self, "ROIs Added",
                                      f"Added {added_count} ROI(s) to statistics.")
        else:
            qt.QMessageBox.information(self, "No New ROIs",
                                      "All available ROIs are already in the statistics table.")
    
    def showTimeseries(self):
        """Show the timeseries plot window."""
        self._update_timeseries_plot()
        self._timeseries.show()
    
    def _update_timeseries_plot(self):
        """Update the timeseries plot with current data."""
        self._timeseries.plot.clear()
        
        time_format = self._timeFormatCombo.currentData() if hasattr(self, '_timeFormatCombo') else TIME_FORMAT_FRAMES
        
        # Plot each ROI
        for roi_name in self.statsTable.get_roi_names():
            # Get data based on current mode
            if self._is_live_mode:
                frames, means = self.data_cache.get_live_means(roi_name)
            else:
                frames, means = self.data_cache.get_all_means(roi_name)
            
            if len(frames) > 0:
                # Convert frame numbers based on format
                if time_format == TIME_FORMAT_FRAMES or self._recording_fps is None or self._recording_fps <= 0:
                    x_values = frames
                else:
                    x_values = frames / self._recording_fps  # Convert to seconds
                
                color = self.data_cache.get_color(roi_name)
                curve = self._timeseries.plot.addCurve(x_values, means, legend=roi_name)
                curve.setColor(color)
        
        # Update axis label based on format
        self._update_axis_label()
        
        # Update cursor position
        self.updateCursorPosition(self._current_frame_index)
    
    def registerRoi(self, roi):
        """
        Register a newly created ROI (called when ROI is drawn).
        This is a compatibility method - does nothing as user must manually add ROIs.
        
        Args:
            roi: ROI object
        """
        # In the new system, users must explicitly add ROIs using the + button
        # This prevents automatic addition that caused freezing
        pass
    
    def unregisterRoi(self, roi):
        """
        Unregister a ROI (called when ROI is deleted from manager).
        
        Args:
            roi: ROI object
        """
        roi_name = roi.getName()
        
        # Remove from table if present
        if self.statsTable.has_roi(roi_name):
            # Find and remove row
            for row in range(self.statsTable.table.rowCount()):
                item = self.statsTable.table.item(row, 1)
                if item and item.text() == roi_name:
                    self.statsTable.table.removeRow(row)
                    self.statsTable.roi_names_in_table.discard(roi_name)
                    break
            
            # Remove from cache
            self.data_cache.remove_roi(roi_name)
    
    def cleanup(self):
        """Clean up resources when closing."""
        # Stop computation engine
        if hasattr(self, 'computation_engine'):
            self.computation_engine.stop()
        
        # Close timeseries window
        if hasattr(self, '_timeseries'):
            self._timeseries.close()

