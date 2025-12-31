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

        self.connect_camera_action = qt.QAction("Connect camera", self)
        self.connect_camera_action.triggered.connect(self._camera_connect_menu)

        self.disconnect_camera_action = qt.QAction("Disconnect camera", self)
        self.disconnect_camera_action.triggered.connect(self._stop_camera)

        if os.name == "nt":
            self.camera_dshow_settings_action = qt.QAction("DirectShow Settings", self)
            self.camera_dshow_settings_action.triggered.connect(self._camera_dshow_settings_menu)
        
        self.camera_settings_action = qt.QAction("Camera Settings", self)
        self.camera_settings_action.triggered.connect(self._camera_settings_menu)

        # Create Recording submenu with Start/Stop options
        self.camera_recording_menu = qt.QMenu("Recording", self)
        self.start_recording_action = qt.QAction("Start Recording", self)
        self.start_recording_action.triggered.connect(self._start_recording)
        self.stop_recording_action = qt.QAction("Stop Recording", self)
        self.stop_recording_action.triggered.connect(self._stop_recording)
        self.stop_recording_action.setEnabled(False)  # Disabled until recording starts
        self.camera_recording_menu.addAction(self.start_recording_action)
        self.camera_recording_menu.addAction(self.stop_recording_action)

        if camera_menu is not None:
            camera_menu.addAction(self.connect_camera_action)
            camera_menu.addAction(self.disconnect_camera_action)
            if self.camera_dshow_settings_action is not None:
                camera_menu.addAction(self.camera_dshow_settings_action)
            camera_menu.addAction(self.camera_settings_action)
            camera_menu.addMenu(self.camera_recording_menu)
            camera_menu.aboutToShow.connect(self._update_camera_menu_state)
        
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
        # Hide browser controls initially (until dataset is loaded or recording starts)
        self.view._browser.setVisible(False)
        self.view._browser_label.setVisible(False)

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

            print(f"Loaded dataset with shape {image_dataset.shape} from {file_path}")
            print(image_dataset)
            self.view.setStack(image_dataset)
            self.view.setFrameNumber(0)
            # Show browser controls when dataset is loaded
            self.view._browser.setVisible(True)
            self.view._browser_label.setVisible(True)
        except Exception as e:
            qt.QMessageBox.warning(self, "Failed to load the media", f"Failed to load HDF5 dataset or convert video file to HDF5: {e}")
        
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

    def _set_browse_controls_visible(self, visible):
        """Show or hide the frame browser controls (slider, label, sync button)."""
        self.view._browser.setVisible(visible)
        self.view._browser_label.setVisible(visible)
        if self.syncButton is not None:
            self.syncButton.setVisible(visible)

    def _stop_camera(self):
        """Stop capture loop, timer, and release camera resources."""
        # Stop timer
        if hasattr(self, "timer") and self.timer is not None:
            try:
                self.timer.stop()
            except Exception:
                pass
            try:
                self.timer.deleteLater()
            except Exception:
                pass
            self.timer = None

        # Hide browser controls
        self._set_browse_controls_visible(False)

        # Remove sync button
        if self.syncButton is not None:
            try:
                self.syncButton.deleteLater()
            except Exception:
                pass
            self.syncButton = None

        # Disconnect resize signal
        try:
            self.dataResized.disconnect(self.update_dataset)
        except Exception:
            pass

        # Clear plot stack if applicable
        if hasattr(self, "view") and isinstance(self.view, StackView):
            try:
                self.view.setStack(None)
            except Exception:
                pass

        # Release camera
        if self.camera is not None:
            try:
                self.camera.stop_recording()
            except Exception:
                pass
            try:
                self.camera.cleanup()
            except Exception:
                pass
            self.camera = None

    def _camera_init(self, port, backend, name, fps):
        try:
            # Stop any existing camera/session before reinitializing
            self._stop_camera()
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
        is_recording = is_connected and self.camera.is_recording
        
        self.disconnect_camera_action.setEnabled(is_connected)
        self.camera_settings_action.setEnabled(is_connected)
        self.camera_recording_menu.setEnabled(is_connected)
        self.start_recording_action.setEnabled(is_connected and not is_recording)
        self.stop_recording_action.setEnabled(is_connected and is_recording)
        if self.camera_dshow_settings_action is not None:
            self.camera_dshow_settings_action.setEnabled(is_connected)

    def _sync_camera(self):
        self.view.setFrameNumber(self.camera.getCurrentFrame())

    def _start_recording(self):
        """Start recording: show file dialog, then begin HDF5 capture and bind dataset to StackView."""
        if self.camera is None:
            return
        
        # Get default path from camera
        default_path = self.camera.get_default_recording_path()
        default_dir = os.path.dirname(default_path)
        default_name = os.path.basename(default_path)
        
        # Show save file dialog
        file_path, _ = qt.QFileDialog.getSaveFileName(
            self,
            "Save Recording As",
            os.path.join(default_dir, default_name),
            "HDF5 Files (*.h5);;All Files (*)"
        )
        
        if not file_path:
            return  # User cancelled
        
        # Ensure .h5 extension
        if not file_path.endswith('.h5'):
            file_path += '.h5'
        
        # Start recording
        self.camera.start_recording(file_path)
        
        # Bind the HDF5 dataset to the StackView for live browsing during recording
        if self.camera.image_dataset is not None:
            self.view.setStack(self.camera.image_dataset)
            # Show browser controls for navigating recorded frames
            self._set_browse_controls_visible(True)
            # Check sync by default so user sees live recording
            if self.syncButton is not None:
                self.syncButton.setChecked(True)
        
        # Update menu state
        self.start_recording_action.setEnabled(False)
        self.stop_recording_action.setEnabled(True)

    def _stop_recording(self):
        """Stop recording and switch back to live preview mode."""
        if self.camera is None:
            return
        
        # Clear StackView before stopping to prevent access to closed dataset
        self.view.setStack(None)
        
        file_path = self.camera.stop_recording()
        
        # Hide browser controls - back to live preview mode
        self._set_browse_controls_visible(False)
        
        if file_path and os.path.exists(file_path):
            qt.QMessageBox.information(self, "Recording Complete",
                f"Recording saved to:\n{file_path}")
        
        # Update menu state
        self.start_recording_action.setEnabled(True)
        self.stop_recording_action.setEnabled(False)

    def _camera_loop(self):
        if self.camera is not None and self.camera.cap.isOpened():
            self.camera.capture_frame()
            
            if self.camera.is_recording and self.camera.image_dataset is not None:
                # Recording mode: update StackView with the HDF5 dataset
                # Only rebind if dataset was resized
                current_stack = self.view.getStack(copy=False, returnNumpyArray=False)
                if current_stack is None or current_stack[0] is not self.camera.image_dataset:
                    self.view.setStack(self.camera.image_dataset)
                
                # Update browser range to show new frames
                frame_count = self.camera.frame_index
                if frame_count > 0:
                    self.view._browser.setRange(0, frame_count - 1)
                
                # Auto-sync to latest frame if sync button is checked
                if self.syncButton is not None and self.syncButton.isChecked():
                    self.view.setFrameNumber(max(0, frame_count - 1))
            else:
                # Live preview mode: update the plot with latest frame
                if self.camera.latest_frame is not None:
                    frame = self.camera.latest_frame[0] if self.camera.latest_frame.ndim == 3 else self.camera.latest_frame
                    self.current_frame = frame
                    self.plot.addImage(self.current_frame, replace=True, resetzoom=False)
            
    def _about_menu(self):
        aw = AboutWindow(self)
        aw.show()

    def update_dataset(self, plot, dataset):
        """Update the plot with the new dataset"""
        framenum = plot.getFrameNumber()
        plot.setStack(dataset)
        plot.setFrameNumber(framenum)

    def closeEvent(self, event):
        """Ensure camera resources are released on window close."""
        self._stop_camera()
        super().closeEvent(event)

def main():
    app = qt.QApplication([])
    window = _RoiStatsDisplayExWindow()
    window.show()
    app.exec()

if __name__ == "__main__":
    main()