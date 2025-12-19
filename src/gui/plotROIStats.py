import os
from silx.gui import qt
from silx.gui.plot import Plot2D
from silx.gui.plot.StackView import StackView
from silx.gui.colors import Colormap
import time
from camera.opencv_capture import CameraInit
from gui.roiwidget import roiManagerWidget
from gui.statswindow import roiStatsWindow
from gui.about_dialog import AboutWindow
from gui.camera_connect_dialog import CameraConnectWindow
from gui.camera_settings_dialog import CameraSettingsWindow
import gui.file_dialog as file_dialog
from gui.file_dialog import H5Playback

class _RoiStatsDisplayExWindow(qt.QMainWindow):
    """
    Main application window that integrates Plot2D/StackView with ROI management and statistics display.
    """

    """Signal to emit when the data is resized"""
    dataResized = qt.Signal(object, object)

    def __init__(self):
        qt.QMainWindow.__init__(self)
        #self.plot = StackView(parent=self, backend="gl")
        self.setWindowTitle("RHEED Analysis")
        # create a none camera object placeholder
        self.camera = None
        # View for holding objects like StackView, plot for holding the Plot component of the object
        self.view = None
        self.plot = None
        self._init_StackView()

        # create a none sync button placeholder
        self.syncButton = None
        
        # store current frame for stats calculations
        self.current_frame = None
        
        # store playback instance for cleanup
        self.playback = None

        #create a menu bar
        self.menu = qt.QMenuBar(self)
        self.menu.setNativeMenuBar(False)

        # add file menu for video/dataset upload (h5py for now only)
        file_menu = self.menu.addMenu("File")
        video_upload_action = qt.QAction("Video upload", self)
        dataset_upload_action = qt.QAction("H5 Dataset upload", self)
        video_upload_action.triggered.connect(lambda : self._open_file("vid"))
        dataset_upload_action.triggered.connect(lambda : self._open_file("h5"))
        if file_menu is not None:
            file_menu.addAction(video_upload_action)
            file_menu.addAction(dataset_upload_action)

        # add camera setup and launch dropdown
        camera_menu = self.menu.addMenu("Camera")

        connect_camera_action = qt.QAction("Connect camera", self)
        connect_camera_action.triggered.connect(self._camera_connect_menu)

        if os.name == "nt":
            camera_dshow_settings_action = qt.QAction("DirectShow Settings", self)
            camera_dshow_settings_action.triggered.connect(self._camera_dshow_settings_menu)
        
        camera_settings_action = qt.QAction("Camera Settings", self)
        camera_settings_action.triggered.connect(self._camera_settings_menu)

        camera_recording_action = qt.QAction("Recording", self)

        if camera_menu is not None:
            camera_menu.addAction(connect_camera_action)
            if camera_dshow_settings_action is not None:
                camera_menu.addAction(camera_dshow_settings_action)
            camera_menu.addAction(camera_settings_action)
            camera_menu.addAction(camera_recording_action)
            camera_menu.aboutToShow.connect(self._update_camera_menu_state)
        
        # Store menu actions for later enable/disable
        self.camera_settings_action = camera_settings_action
        self.camera_recording_action = camera_recording_action
        self.camera_dshow_settings_action = camera_dshow_settings_action if os.name == "nt" else None
        
        # add about window
        about_action = qt.QAction("About", self)
        about_action.triggered.connect(self._about_menu)
        self.menu.addAction(about_action)

        # add menu to the window
        self.setMenuBar(self.menu)

        """# hidden plot2D for stats
        self._hiddenPlot2D = Plot2D()  # not added to layout
        self._hiddenPlot2D.hide()"""

        # Placeholder; ROI manager will be created when the plot is (re)created
        self._regionManagerWidget = None
        self._roi_manager_initialized = False
        
        # tabWidget for displaying the rois
        self._roisTabWidget = qt.QTabWidget(parent=self)

        # Create ROI manager and attach to tab
        self._regionManagerWidget = roiManagerWidget(parent=self, plot=self.plot)

         # widget for displaying stats results
        self._statsWidget = roiStatsWindow(parent=self, plot=self.plot, stackview=self.view, roimanager=self._regionManagerWidget.roiManager)
        
        #self.view.sigFrameChanged.connect(self._update_hidden_plot)
        self.view.sigFrameChanged.connect(self._statsWidget.updateTimeseriesAsync)
        

        # create Dock widgets
        self._roisTabWidgetDockWidget = qt.QDockWidget(parent=self)
        self._roisTabWidgetDockWidget.setWidget(self._roisTabWidget)
        self.addDockWidget(qt.Qt.DockWidgetArea.RightDockWidgetArea, self._roisTabWidgetDockWidget)

        # create Dock widgets
        self._roiStatsWindowDockWidget = qt.QDockWidget(parent=self)
        self._roiStatsWindowDockWidget.setWidget(self._statsWidget)
        self.addDockWidget(qt.Qt.DockWidgetArea.RightDockWidgetArea, self._roiStatsWindowDockWidget)

        # Connect ROI signal to register ROI automatically
        self._regionManagerWidget.roiManager.sigRoiAdded.connect(self._statsWidget.registerRoi)
        self._regionManagerWidget.roiManager.sigRoiAboutToBeRemoved.connect(self._statsWidget.unregisterRoi)

        # Add ROI tab (will already be added if first creation was in _rebuild_roi_manager)
        if self._roisTabWidget.count() == 0:
            self._roisTabWidget.addTab(self._regionManagerWidget, "2D roi(s)")
        #self._roisTabWidget.addTab(self._curveRoiWidget, "1D roi(s)")

    def _init_StackView(self):
        self.view = StackView(parent=self, backend="gl")
        self.plot = self.view.getPlotWidget()
        self.setCentralWidget(self.view)
        self.view.setKeepDataAspectRatio(True)
        self.view.setYAxisInverted(True)
        self.view._StackView__planeSelection.setVisible(False)
        self.view._StackView__planeSelection.setEnabled(False)
        self.view.setColormap("green")
        # change the plane widget label to a slider label for consistency
        self.view._browser_label.setText("Slider (Frames):")
        qt.QTimer.singleShot(0, self._rebuild_roi_manager)

    def _open_file(self, file_type):
        file_path = file_dialog.open_file_path(file_type)
        if file_path is None:
            return

        try:
            playback = H5Playback(file_path, file_type)
            image_dataset = getattr(playback, "image_dataset", None)
            dataset_size = getattr(playback, "dataset_size", 0)

            if image_dataset is None or dataset_size <= 0:
                qt.QMessageBox.warning(self, "Failed to load the media", "No frames found in the selected file.")
                return

            self._init_StackView()
            print(f"Loaded dataset with shape {image_dataset.shape} from {file_path}")
            print(image_dataset)
            self.view.setStack(image_dataset)
            self.view.setFrameNumber(0)
        except Exception as e:
            qt.QMessageBox.warning(self, "Failed to load the media", f"Failed to load HDF5 dataset or convert video file to HDF5: {e}")
            self._init_Plot2D()
        
    def _camera_connect_menu(self):
        self.cmw = CameraConnectWindow()
        self.cmw.show()
        self.cmw.backendValuePicked.connect(self._camera_init)

    def _camera_dshow_settings_menu(self):
        if self.camera is not None:
            if self.camera.getBackend() == "DSHOW":
                self.camera.openDSHOWSettings()
    
    def _camera_settings_menu(self):
        if self.camera is not None:
            self.cmw = CameraSettingsWindow(camera_init=self.camera)
            self.cmw.show()

    def _camera_init(self, port, backend, name, fps):
        try:
            if self.camera is not None:
                # Clear the StackView reference to the old dataset BEFORE cleanup
                self.view.setStack(None)
                self.camera.cleanup()
                self.camera = None
            print(f"Initializing camera on port {port} with backend {backend} and name {name}")
            self.camera = CameraInit(2000, port, backend, name, fps)

            if self.syncButton is not None:
                self.syncButton.deleteLater()
                self.syncButton = None
            # create an icon button to sync the stackview and its FPS speed with the camera
            self.syncButton = qt.QPushButton("Sync", self)
            app_style = self.style()
            icon = qt.QIcon()
            if app_style is not None:
                icon = app_style.standardIcon(qt.QStyle.StandardPixmap.SP_BrowserReload)
            self.syncButton.setIcon(icon)
            self.syncButton.setLayoutDirection(qt.Qt.LayoutDirection.RightToLeft)
            self.syncButton.setIconSize(qt.QSize(20, 20))
            self.syncButton.setToolTip("Sync the stackview with the camera")
            self.syncButton.setCheckable(True)
            self.syncButton.clicked.connect(self._sync_camera)
            self.syncButton.toggled.connect(self._sync_camera)
            # add the sync button to the slider browser layout
            self.view._browser.mainLayout.addWidget(self.syncButton)
            self.view._browser.setFrameRate(int(self.camera.getFPS()))
            self.view._browser.setContentsMargins(0, 0, 15, 0)

            # populate the stackview with the live single-frame buffer
            if self.camera.latest_frame is not None:
                print(self.camera.latest_frame.shape)
                # Remove first dimension if present (1, H, W) -> (H, W)
                frame = self.camera.latest_frame[0] if self.camera.latest_frame.ndim == 3 else self.camera.latest_frame
                self.current_frame = frame
                self.plot.addImage(frame)
                #self._hiddenPlot2D.addImage(frame)
                self.view.setStack(self.camera.latest_frame)
                self.view.setFrameNumber(0)

            # connect the resize callback to the camera
            #self.camera.on_resize = lambda new_dataset: self.dataResized.emit(self.plot, new_dataset)

            # connect the resize signal to the plot
            self.dataResized.connect(self.update_dataset)
            
            # create and start a timer to capture frames at the camera FPS rate
            self.timer = qt.QTimer(self)
            # Compute integer interval from FPS
            try:
                fps_val = float(self.camera.getFPS())
                if fps_val > 0:
                    interval_ms = int(round(1000 / fps_val))
                else:
                    interval_ms = 1000  # ~1 FPS fallback
            except Exception:
                interval_ms = 1000  # fallback if getFPS fails

            self.timer.start(interval_ms)
            self.timer.timeout.connect(self._camera_loop)

        except Exception as e:
            print(f"Failed to initialize camera: {e}")
            self.camera = None


    def _update_camera_menu_state(self):
        """Update camera menu actions based on camera connection state."""
        is_connected = self.camera is not None and self.camera.cap is not None and self.camera.cap.isOpened()
        self.camera_settings_action.setEnabled(is_connected)
        self.camera_recording_action.setEnabled(is_connected)
        if self.camera_dshow_settings_action is not None:
            self.camera_dshow_settings_action.setEnabled(is_connected)

    def _sync_camera(self):
        self.view.setFrameNumber(self.camera.getCurrentFrame())

    def _camera_loop(self):
        if self.camera is not None and self.camera.cap.isOpened():
            self.camera.capture_frame()
            # Update live display from the single-frame buffer: rebind to trigger UI refresh
            if self.camera.latest_frame is not None:
                print("Updating live camera frame in plot")
                # Remove first dimension if present (1, H, W) -> (H, W)
                frame = self.camera.latest_frame[0] if self.camera.latest_frame.ndim == 3 else self.camera.latest_frame
                self.current_frame = frame
                self.plot.addImage(frame)
                #self._hiddenPlot2D.addImage(frame)
            # Sync stackview frame number with camera frame number
            if self.syncButton is not None and self.syncButton.isChecked():
                self._sync_camera()
            
    def _about_menu(self):
        aw = AboutWindow(self)
        aw.show()

    """def _update_hidden_plot(self, index):
        try:
            if isinstance(self.plot, StackView):
                frame = self.plot._stack[self.plot.getFrameNumber()]
                if frame is None or (hasattr(frame, 'size') and frame.size == 0):
                    return
                # Ensure frame is 2D for Plot2D
                if frame.ndim == 3:
                    frame = frame[0] if frame.shape[0] == 1 else frame
                self._hiddenPlot2D.addImage(frame)
            # For Plot2D, hidden plot is already updated in camera loop
            self._statsWidget.statsWidget._updateAllStats()
        except Exception as e:
            print(f"Failed to update hidden plot: {e}")"""

    def update_dataset(self, plot, dataset):
        """Update the plot with the new dataset"""
        framenum = plot.getFrameNumber()
        plot.setStack(dataset)
        plot.setFrameNumber(framenum)

def main():
    app = qt.QApplication([])
    window = _RoiStatsDisplayExWindow()
    window.show()
    app.exec()

if __name__ == "__main__":
    main()