"""
Custom Stats Table Widget
Replacement for silx ROIStatsWidget with +/- buttons and ROI selection.
"""
from silx.gui import qt
import numpy as np


class ROISelectionDialog(qt.QDialog):
    """Dialog for selecting which ROI to add to statistics."""
    
    def __init__(self, available_rois, already_added_names, parent=None):
        """
        Create ROI selection dialog.
        
        Args:
            available_rois: List of ROI objects from ROI manager
            already_added_names: Set of ROI names already in stats table
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("Select ROI for Analysis")
        self.selected_roi = None
        
        layout = qt.QVBoxLayout(self)
        
        # Info label
        info_label = qt.QLabel("Select an ROI to add to the statistics table:")
        layout.addWidget(info_label)
        
        # List widget for ROI selection
        self.roi_list = qt.QListWidget()
        
        # Filter out ROIs already added
        self.available_rois = []
        for roi in available_rois:
            roi_name = roi.getName()
            if roi_name not in already_added_names:
                self.available_rois.append(roi)
                
                # Create list item with color indicator
                item = qt.QListWidgetItem(roi_name)
                
                # Set color
                color = roi.getColor() if hasattr(roi, 'getColor') else qt.QColor(255, 255, 255)
                item.setForeground(color)
                
                # Add icon with ROI type
                roi_type = type(roi).__name__.replace('ROI', '')
                item.setText(f"{roi_name} ({roi_type})")
                
                self.roi_list.addItem(item)
        
        if len(self.available_rois) == 0:
            empty_label = qt.QLabel("No ROIs available (all are already added)")
            layout.addWidget(empty_label)
        
        layout.addWidget(self.roi_list)
        
        # Buttons
        button_box = qt.QDialogButtonBox(
            qt.QDialogButtonBox.Ok | qt.QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        # Enable OK only when selection is made
        ok_button = button_box.button(qt.QDialogButtonBox.Ok)
        if ok_button is not None:
            ok_button.setEnabled(False)
            self.roi_list.itemSelectionChanged.connect(
                lambda: ok_button.setEnabled(len(self.roi_list.selectedItems()) > 0)
            )
        
        # Double-click to select
        self.roi_list.itemDoubleClicked.connect(self.accept)
        
        self.resize(400, 300)
    
    def accept(self):
        """Handle dialog acceptance."""
        selected_items = self.roi_list.selectedItems()
        if len(selected_items) > 0:
            selected_index = self.roi_list.row(selected_items[0])
            self.selected_roi = self.available_rois[selected_index]
        super().accept()


class CustomROIStatsTable(qt.QWidget):
    """Custom stats table widget with +/- buttons for ROI management."""
    
    # Signals
    roiAddRequested = qt.Signal(object)  # ROI object
    roiRemoveRequested = qt.Signal(str)  # ROI name
    
    def __init__(self, roi_manager, parent=None):
        """
        Create custom stats table.
        
        Args:
            roi_manager: RegionOfInterestManager instance
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.roi_manager = roi_manager
        self.roi_names_in_table = set()  # Track which ROIs are added
        
        # Main layout
        layout = qt.QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(5)
        
        # Toolbar with +/- buttons
        toolbar = qt.QHBoxLayout()
        
        self.add_button = qt.QPushButton("+")
        self.add_button.setToolTip("Add ROI to statistics")
        self.add_button.setMaximumWidth(40)
        
        self.remove_button = qt.QPushButton("-")
        self.remove_button.setToolTip("Remove selected ROI from statistics")
        self.remove_button.setMaximumWidth(40)
        self.remove_button.setEnabled(False)  # Disabled until selection
        
        toolbar.addWidget(qt.QLabel("ROI Statistics:"))
        toolbar.addStretch()
        toolbar.addWidget(self.add_button)
        toolbar.addWidget(self.remove_button)
        
        layout.addLayout(toolbar)
        
        # Table widget
        self.table = qt.QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Color", "ROI Name", "Mean", "Progress"])
        
        # Set column widths
        self.table.setColumnWidth(0, 30)   # Color indicator
        self.table.setColumnWidth(1, 150)  # ROI name
        self.table.setColumnWidth(2, 80)   # Mean value
        self.table.setColumnWidth(3, 120)  # Progress
        
        # Table settings
        self.table.setSelectionBehavior(qt.QTableWidget.SelectRows)
        self.table.setSelectionMode(qt.QTableWidget.SingleSelection)
        self.table.setEditTriggers(qt.QTableWidget.NoEditTriggers)
        
        layout.addWidget(self.table)
        
        # Connect signals
        self.add_button.clicked.connect(self._on_add_clicked)
        self.remove_button.clicked.connect(self._on_remove_clicked)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
    
    def _on_add_clicked(self):
        """Handle add button click - show ROI selection dialog."""
        if self.roi_manager is None:
            qt.QMessageBox.warning(self, "No ROI Manager", 
                                  "ROI manager is not available.")
            return
        
        available_rois = self.roi_manager.getRois()
        
        if len(available_rois) == 0:
            qt.QMessageBox.information(self, "No ROIs", 
                                      "No ROIs have been created yet. "
                                      "Draw ROIs on the image first.")
            return
        
        # Show selection dialog
        dialog = ROISelectionDialog(available_rois, self.roi_names_in_table, self)
        
        if dialog.exec() and dialog.selected_roi is not None:
            roi = dialog.selected_roi
            roi_name = roi.getName()
            
            # Add row to table
            self._add_table_row(roi)
            
            # Track that this ROI is added
            self.roi_names_in_table.add(roi_name)
            
            # Emit signal for computation
            self.roiAddRequested.emit(roi)
    
    def _on_remove_clicked(self):
        """Handle remove button click."""
        selected_rows = self.table.selectedItems()
        
        if len(selected_rows) == 0:
            return
        
        row = self.table.currentRow()
        
        if row < 0:
            return
        
        # Get ROI name from table
        name_item = self.table.item(row, 1)
        if name_item is None:
            return
        
        roi_name = name_item.text()
        
        # Confirm removal
        reply = qt.QMessageBox.question(
            self, "Remove ROI",
            f"Remove '{roi_name}' from statistics?",
            qt.QMessageBox.Yes | qt.QMessageBox.No,
            qt.QMessageBox.No
        )
        
        if reply == qt.QMessageBox.Yes:
            # Remove from table
            self.table.removeRow(row)
            
            # Remove from tracking set
            self.roi_names_in_table.discard(roi_name)
            
            # Emit signal
            self.roiRemoveRequested.emit(roi_name)
    
    def _on_selection_changed(self):
        """Handle table selection change."""
        has_selection = len(self.table.selectedItems()) > 0
        self.remove_button.setEnabled(has_selection)
    
    def _add_table_row(self, roi):
        """
        Add a row to the table for an ROI.
        
        Args:
            roi: ROI object
        """
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        roi_name = roi.getName()
        color = roi.getColor() if hasattr(roi, 'getColor') else qt.QColor(255, 255, 255)
        
        # Color indicator (colored square)
        color_widget = qt.QWidget()
        color_layout = qt.QHBoxLayout(color_widget)
        color_layout.setContentsMargins(5, 5, 5, 5)
        color_label = qt.QLabel()
        color_label.setFixedSize(20, 20)
        color_label.setStyleSheet(f"background-color: {color.name()}; border: 1px solid black;")
        color_layout.addWidget(color_label)
        self.table.setCellWidget(row, 0, color_widget)
        
        # ROI name
        name_item = qt.QTableWidgetItem(roi_name)
        self.table.setItem(row, 1, name_item)
        
        # Mean value (initially empty)
        mean_item = qt.QTableWidgetItem("...")
        mean_item.setTextAlignment(qt.Qt.AlignCenter)
        self.table.setItem(row, 2, mean_item)
        
        # Progress (initially 0%)
        progress_item = qt.QTableWidgetItem("0%")
        progress_item.setTextAlignment(qt.Qt.AlignCenter)
        self.table.setItem(row, 3, progress_item)
    
    def update_mean_value(self, roi_name, mean_value):
        """
        Update the mean value display for an ROI.
        
        Args:
            roi_name: String ROI name
            mean_value: Float mean intensity value
        """
        # Find row with this ROI name
        for row in range(self.table.rowCount()):
            name_item = self.table.item(row, 1)
            if name_item and name_item.text() == roi_name:
                mean_item = self.table.item(row, 2)
                if mean_item:
                    mean_item.setText(f"{mean_value:.2f}")
                break
    
    def update_progress(self, roi_name, computed_frames, total_frames):
        """
        Update the progress display for an ROI.
        
        Args:
            roi_name: String ROI name
            computed_frames: Number of frames computed
            total_frames: Total frames in dataset
        """
        # Find row with this ROI name
        for row in range(self.table.rowCount()):
            name_item = self.table.item(row, 1)
            if name_item and name_item.text() == roi_name:
                progress_item = self.table.item(row, 3)
                if progress_item:
                    if total_frames > 0:
                        percent = int(computed_frames / total_frames * 100)
                        progress_item.setText(f"{percent}%")
                    else:
                        progress_item.setText("N/A")
                break
    
    def mark_complete(self, roi_name):
        """
        Mark an ROI as fully computed.
        
        Args:
            roi_name: String ROI name
        """
        self.update_progress(roi_name, 1, 1)  # 100%
    
    def clear_all_rois(self):
        """Remove all ROIs from the table."""
        # Check if there are any ROIs to clear
        if len(self.roi_names_in_table) == 0:
            qt.QMessageBox.information(
                self, 
                "No ROIs to Clear",
                "There are no ROIs in the statistics table to clear."
            )
            return
        
        # Show confirmation dialog
        reply = qt.QMessageBox.question(
            self,
            "Clear All ROIs?",
            f"This action will remove all {len(self.roi_names_in_table)} ROI(s) from the statistics table.\n\n"
            "This will:\n"
            "• Remove ROIs from the current statistics display\n"
            "• Clear all computed timeseries data\n"
            "• Stop any ongoing background computations\n\n"
            "Are you sure you want to continue?",
            qt.QMessageBox.Yes | qt.QMessageBox.No,
            qt.QMessageBox.No
        )
        
        if reply != qt.QMessageBox.Yes:
            return
        
        # Get all ROI names before clearing
        roi_names = list(self.roi_names_in_table)
        
        # Clear table
        self.table.setRowCount(0)
        self.roi_names_in_table.clear()
        
        # Emit remove signals for each
        for roi_name in roi_names:
            self.roiRemoveRequested.emit(roi_name)
    
    def get_roi_names(self):
        """Get list of ROI names currently in the table."""
        return list(self.roi_names_in_table)
    
    def has_roi(self, roi_name):
        """Check if ROI is in the table."""
        return roi_name in self.roi_names_in_table
