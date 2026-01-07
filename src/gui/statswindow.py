"""
ROI Statistics Window
Custom implementation with non-blocking computation and timeseries plotting.
"""
from silx.gui import qt
import numpy as np
from silx.gui.plot import Plot1D
from silx.gui.plot.StackView import StackView
from gui.custom_stats_table import CustomROIStatsTable
from gui.roi_data_cache import ROIDataCache
from gui.roi_computation_engine import ROIComputationEngine


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
        
        # Create custom stats table
        self.statsTable = CustomROIStatsTable(self._roiManager, parent=self)
        
        # Timeseries plot window (hidden by default)
        self._timeseries = qt.QWidget()
        timeseries_layout = qt.QVBoxLayout()
        self._timeseries.setLayout(timeseries_layout)
        self._timeseries.setWindowTitle("ROI Time Series")
        self._timeseries.plot = Plot1D()
        timeseries_layout.addWidget(self._timeseries.plot)
        self._timeseries.plot.setGraphXLabel("Frame number")
        self._timeseries.plot.setGraphYLabel("Intensity")
        self._timeseries.plot.setGraphTitle("ROI Time Series")
        self._timeseries.plot.setKeepDataAspectRatio(False)
        self._timeseries.plot.setActiveCurveHandling(False)
        self._timeseries.plot.setBackend("opengl")
        self._timeseries.plot.setGraphGrid(False)
        
        # Enable legend with colored boxes - access legend widget and show it
        legend_widget = self._timeseries.plot.getLegendsDockWidget()
        if legend_widget is not None:
            legend_widget.show()
        
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
    
    def setDataset(self, dataset):
        """
        Set the dataset for ROI analysis.
        
        Args:
            dataset: Numpy array or h5py dataset with shape (N, H, W) or (H, W)
        """
        self._dataset = dataset
        
        if dataset is not None:
            if dataset.ndim == 3:
                self._total_frames = dataset.shape[0]
            elif dataset.ndim == 2:
                self._total_frames = 1
            else:
                self._total_frames = 0
        else:
            self._total_frames = 0
        
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
            self.computation_engine.queue_current_frame(frame_index, frame_data, roi_list)
    
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
        
        # Plot each ROI
        for roi_name in self.statsTable.get_roi_names():
            frames, means = self.data_cache.get_all_means(roi_name)
            
            if len(frames) > 0:
                color = self.data_cache.get_color(roi_name)
                curve = self._timeseries.plot.addCurve(frames, means, legend=roi_name)
                curve.setColor(color)
    
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

