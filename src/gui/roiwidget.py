from silx.gui import qt
from silx.gui.plot.tools.roi import RegionOfInterestManager, RegionOfInterestTableWidget, RoiModeSelectorAction
from silx.io import dictdump
import gui.roidictionary as roidict
import datetime

class roiManagerWidget(qt.QWidget):

    # List of colors to be assigned to ROIs
    colors = [qt.QColor(255, 0, 0), qt.QColor(0, 255, 0), qt.QColor(0, 0, 255), qt.QColor(255, 255, 0), 
                qt.QColor(255, 0, 255), qt.QColor(0, 255, 255), qt.QColor(255, 255, 100), qt.QColor(0, 0, 50),
                qt.QColor(128, 0, 0), qt.QColor(0, 128, 0), qt.QColor(0, 0, 128), qt.QColor(128, 128, 0),
                qt.QColor(128, 0, 128), qt.QColor(0, 128, 128), qt.QColor(128, 128, 128), qt.QColor(64, 64, 64),
                qt.QColor(255, 128, 0), qt.QColor(128, 255, 0), qt.QColor(0, 128, 255), qt.QColor(128, 0, 255),
                qt.QColor(255, 0, 128), qt.QColor(0, 255, 128), qt.QColor(128, 128, 255), qt.QColor(128, 255, 128),
                qt.QColor(255, 128, 128), qt.QColor(128, 128, 128), qt.QColor(128, 255, 255), qt.QColor(255, 128, 255),
                qt.QColor(255, 255, 128), qt.QColor(128, 128, 255), qt.QColor(255, 128, 128), qt.QColor(128, 255, 128),
                qt.QColor(128, 128, 128), qt.QColor(255, 255, 255), qt.QColor(0, 0, 0)]

    def __init__(self, parent=None, plot=None):
        """
        Create a composite widget that embeds the 2D ROI manager and table,
        and adds Save/Load buttons.
        """
        assert plot is not None
        super().__init__(parent)
        self.plot = plot

        # Main layout for the custom widget
        layout = qt.QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 5, 5)
        layout.setSpacing(5)
        
        # Create embed ROIs checkbox
        self.embedCheckbox = qt.QCheckBox("Embed ROIs in the HDF5 dataset", self)
        self.embedCheckbox.setEnabled(False)
        self.embedCheckbox.setToolTip("Start recording or open a dataset to enable")
        self.embedCheckbox.setChecked(False)
        
        # Create a horizontal layout for the save/load buttons
        btnLayout = qt.QHBoxLayout()
        self.clearButton = qt.QPushButton("Clear All", self)
        self.saveButton = qt.QPushButton("Save", self)
        self.loadButton = qt.QPushButton("Load", self)
        btnLayout.addStretch(1)
        btnLayout.addWidget(self.clearButton)
        btnLayout.addWidget(self.loadButton)
        btnLayout.addWidget(self.saveButton)
        
        # Create the silx 2D ROI manager and table
        print(self.plot)
        self.roiManager = RegionOfInterestManager(parent=self.plot)
        self._roiTable = RegionOfInterestTableWidget()
        self._roiTable.setRegionOfInterestManager(self.roiManager)

        # Create a toolbar containing buttons for all ROI 'drawing' modes
        self._roiToolbar = qt.QToolBar()
        #self._roiToolbar.setIconSize(qt.QSize(32, 32))

        for roiClass in self.roiManager.getSupportedRoiClasses():
        # Create a tool button and associate it with the QAction of each mode
            self._roiToolbar.addAction(self.roiManager.getInteractionModeAction(roiClass))

        modeSelectorAction = RoiModeSelectorAction()
        modeSelectorAction.setRoiManager(self.roiManager)
        
        # Add the ROI table widget to the layout
        layout.addWidget(self._roiToolbar)
        layout.addWidget(self._roiTable)
        layout.addWidget(self.embedCheckbox)
        layout.addLayout(btnLayout)

        #automatical color and name incrementation
        self.roiManager.sigRoiAdded.connect(self._onRoiAdded)
        
        # Connect the button signals to the saving/loading methods and clear method
        self.loadButton.clicked.connect(self.loadROIs)
        self.saveButton.clicked.connect(self.saveROIs)
        self.clearButton.clicked.connect(self.clearROIs)
    
    # File dialog to save to file
    def saveROIs(self):
        # Use a file dialog to let the user choose a file name
        dialog = qt.QFileDialog(self)
        dialog.setAcceptMode(qt.QFileDialog.AcceptSave)
        dialog.setNameFilters(["INI File (*.ini)", "JSON File (*.json)"])
        if dialog.exec():
            filename = f"roi_save_{datetime.datetime.now().strftime('%d-%m-%Y_%H-%M-%S')}"
            # Automatically add extension if missing (based on the filter)
            selectedFilter = dialog.selectedNameFilter()
            extension = ".ini" if "INI" in selectedFilter else ".json"
            if not filename.endswith(extension):
                filename += extension
            self._save(filename)

    def _onRoiAdded(self, roi):
        print(f"DEBUG _onRoiAdded: ROI added, now have {len(self.roiManager.getRois())} ROIs")
        roi.setName(f"ROI {len(self.roiManager.getRois())}")
        # set the colors of the ROIs from the list of colors above
        roi.setColor(self.colors[len(self.roiManager.getRois()) % len(self.colors)])
    
    # Save ROIs to a file
    def _save(self, filename):
        # Collect ROI data similar to the curvesROI widget's save method
        # Save the ROI data to a file
        rois = self.roiManager.getRois()
        roidict.save_rois_to_file(rois, filename)
    
    # File dialog to load from file
    def loadROIs(self):
        dialog = qt.QFileDialog(self)
        dialog.setAcceptMode(qt.QFileDialog.AcceptOpen)
        dialog.setNameFilters(["INI File (*.ini)", "JSON File (*.json)"])
        if dialog.exec():
            filename = dialog.selectedFiles()[0]
            self._load(filename)
    
    # Load ROIs from a file
    def _load(self, filename):
        # Load the ROI data from a file
        rois = roidict.load_rois_from_file(filename)
        for each in rois:
            self.roiManager.addRoi(each)

    # Clear all ROIs from the plot
    def clearROIs(self):
        for each in self.roiManager.getRois():
            self.roiManager.removeRoi(each)

    def setEmbedEnabled(self, enabled, checked=True):
        """Enable or disable the embed checkbox and optionally set its state."""
        self.embedCheckbox.setEnabled(enabled)
        if enabled:
            self.embedCheckbox.setChecked(checked)
            self.embedCheckbox.setToolTip("ROIs will be saved to the dataset when closed")
        else:
            self.embedCheckbox.setToolTip("Start recording or open a dataset to enable")

    def isEmbedChecked(self):
        """Return whether the embed checkbox is checked."""
        return self.embedCheckbox.isChecked() and self.embedCheckbox.isEnabled()

    def getRois(self):
        """Return the list of current ROIs."""
        return self.roiManager.getRois()

    def hasRois(self):
        """Return whether there are any ROIs."""
        return len(self.roiManager.getRois()) > 0

    def loadROIsFromList(self, rois):
        """Load ROIs from a list of ROI objects (clears existing first)."""
        self.clearROIs()
        for roi in rois:
            self.roiManager.addRoi(roi)