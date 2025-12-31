from silx.gui import qt
from silx.gui.plot.ROIStatsWidget import ROIStatsWidget
from silx.gui.plot.StatsWidget import _ScalarFieldViewWrapper
import numpy
from silx.gui.plot import Plot1D
from silx.gui.plot.StackView import StackView

class roiStatsWindow(qt.QWidget):
    """Window that embeds the stats widget and button for launching time series of the ROIs."""

    STATS = [
    ("mean", numpy.mean)
    ]

    def __init__(self, parent=None, plot=None, stackview=None, roimanager=None):
        """
        Create a window that embeds the stats widget and button for showing _timeseries of the ROIs.
        stackview can be either a StackView or Plot2D instance.
        """
        assert plot is not None
        qt.QMainWindow.__init__(self, parent)
        self._plot2d = plot
        self._view = stackview
        layout = qt.QVBoxLayout(self)
        self.statsWidget = ROIStatsWidget(plot=self._plot2d)
        self._roiManager = roimanager
        
        self._timeseries = qt.QWidget()
        self._timeseries.setLayout(qt.QVBoxLayout())
        self._timeseries.setWindowTitle("ROI Time Series")
        self._timeseries.plot = Plot1D()
        self._timeseries.layout().addWidget(self._timeseries.plot)
        self._timeseries.plot.setGraphXLabel("Frame number")
        self._timeseries.plot.setGraphYLabel("Intensity")
        self._timeseries.plot.setGraphTitle("ROI Time Series")
        self._timeseries.plot.setKeepDataAspectRatio(False)
        self._timeseries.plot.setActiveCurveHandling(False)
        self._timeseries.plot.setBackend("opengl")
        self._timeseries.plot.setGraphGrid(False)
        self._timeseries.hide()

        self._meanarray = {[roi.getName()]: numpy.array([]) for roi in self.statsWidget._rois}
        self._first_frames = {[roi.getName()]: int for roi in self.statsWidget._rois}

        ''' Main layout for the custom widget
        layout = qt.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        '''
        
        # Create a horizontal layout for the time series button
        btnLayout = qt.QHBoxLayout()
        btnLayout.setAlignment(qt.Qt.AlignmentFlag.AlignVCenter)
        timeseriesbutton = qt.QPushButton("Show Timeseries Plot", self)
        roisbutton = qt.QPushButton("Add All ROIs", self)
        btnLayout.addStretch(2)
        btnLayout.addWidget(roisbutton)
        btnLayout.addWidget(timeseriesbutton)

        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(5)
        layout.addWidget(self.statsWidget)
        layout.addLayout(btnLayout)

        self.statsWidget._setUpdateMode("manual")
        self.setStats(self.STATS)
        timeseriesbutton.clicked.connect(self.showTimeseries)
        roisbutton.clicked.connect(self.addAllRois)

    def addAllRois(self):
        """Add all ROIs to the stats widget and update the plot."""
        # Get all ROIs from the ROI manager
        try : 
            if self._roiManager is None:
                return
            rois = self._roiManager.getRois()
            for roi in rois:
                self.statsWidget.addItem(plotItem=self._plot2d.getImage(), roi=roi)
        except Exception:
            qt.QMessageBox.warning(self, "No Plot2D","It is not possible to add ROIs until there is a "+
                                   "base plot to make analysis from.")
            return

        # Update the timeseries plot with the new ROIs
    
    def showTimeseries(self):
            self.updateTimeseriesAsync()
            self._timeseries.show()
            if self._view is not None:
                # Connect appropriate signal based on view type
                if isinstance(self._view, StackView):
                    self._view.sigStackChanged.connect(self._dataset_size_changed)
                else:
                    # For Plot2D, connect to active image changed signal
                    self._view.sigActiveImageChanged.connect(self._dataset_size_changed)

    def _dataset_size_changed(self):
        """Update the x-axis limits of the time series plot when the dataset size changes."""
        #(data, info) = self._view.getStack(copy=True, returnNumpyArray=True)
        #print(data.size)
        #self._timeseries.plot.setGraphXLimits(0, data.size)

    def _getMeanForROI(self, roi):
        print(roi)
        """Return the current computed mean stat for the given ROI.
        This reads the value from the internal _statsROITable. For 0D ROIs it returns the value.
        """
        handler = self.statsWidget.getStatsHandler()
        print(handler.stats)
        handler.stats.add() 
        table = self.statsWidget._statsROITable
        meanColumn = None
        # Find the column index for the 'mean' stat.
        for col in range(table.columnCount()):
            header = table.horizontalHeaderItem(col)
            if header and header.data(qt.Qt.ItemDataRole.UserRole) == 'mean':
                meanColumn = col
                break

        if meanColumn is None:
            print("Mean column not found")
            return None

        # Now locate the row corresponding to the ROI by matching its name.
        meanValue = None
        for row in range(table.rowCount()):
            roiItem = table.item(row, 2)  # Column 2 is used for ROI name.
            if roiItem and roiItem.text() == roi.getName():
                meanItem = table.item(row, meanColumn)
                if meanItem:
                    try:
                        #condition check for single point ROIs
                        if meanItem.text() != "":
                            meanValue = float(meanItem.text())
                    except ValueError:
                        print("Could not convert mean value to float")
                        meanValue = None
                break

        return meanValue


    def setStats(self, stats):
        self.statsWidget.setStats(stats=stats)

        self.roiUpdateTimer = qt.QTimer(self)
        self.roiUpdateTimer.timeout.connect(lambda: self.statsWidget._updateAllStats(is_request=True))
        self.roiUpdateTimer.start(50)

    def addItem(self, item, roi):
        self.statsWidget.addItem(roi=roi, plotItem=item)

    def removeItem(self, item):
        self.statsWidget.removeItem(item)

    def registerRoi(self, roi):
        #Register a newly created ROI with the stats widget.
        self.statsWidget.registerROI(roi)

    def unregisterRoi(self, roi):
        print("not actually unregistering any roi")
        #Unregister a ROI in the stats widget.
        #self.statsWidget._statsROITable.unregisterROI(roi)
        #self._statsWidget

    def updateTimeseriesAsync(self):
        
        if self._view is None:
            print("Warning: view not set for timeseries update")
            return
        
        # Get frame number based on view type
        if isinstance(self._view, StackView):
            framenum = self._view.getFrameNumber()
        else:
            # For Plot2D, frame number is 0 to signalize real-time view mode
            framenum = None
        
        self.worker = TimeseriesWorker(
            rois=self.statsWidget._rois,
            meanarray=self._meanarray,
            first_frames=self._first_frames,
            getMeanFunc=self._getMeanForROI,
            frameNumber=framenum
        )
        self.worker.updated.connect(self._plotTimeseries)
        self.worker.start()

    def _plotTimeseries(self, data):
        self._timeseries.plot.clear()
        for name, (x, y, color) in data.items():
            self.c = self._timeseries.plot.addCurve(x, y, legend=name)
            self.c.setColor(color)

class TimeseriesWorker(qt.QThread):
    updated = qt.Signal(dict)

    def __init__(self, rois, meanarray, first_frames, getMeanFunc, frameNumber):
        super().__init__()
        self._running = True
        self.rois = rois
        self.meanarray = meanarray
        self.first_frames = first_frames
        self.getMean = getMeanFunc
        if frameNumber is None:
            self.framenum = max((meanarray[roi].size - 1 for roi in meanarray.keys()), default=0) + 1
        else:
            self.framenum = frameNumber

    def run(self):
        result = {}
        for roi in self.rois:
            if not self._running:
                break
            name = roi.getName()
            if name not in self.meanarray:
                self.meanarray[name] = numpy.array([])

            new_value = self.getMean(roi)
            if new_value is not None:
                if self.meanarray[name].size == self.framenum:
                    self.meanarray[name] = numpy.resize(self.meanarray[name], self.framenum + 2)
                self.meanarray[name][self.framenum] = new_value

                x = numpy.arange(self.framenum + 1)
                y = self.meanarray[name][:self.framenum + 1]

                #if x.size != y.size:
                #    y = numpy.resize(y, x.size)

                result[name] = (x, y, roi.getColor())

        if self._running:
            self.updated.emit(result)

    def quit(self):
        self._running = False
        super().quit()
