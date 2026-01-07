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
import gui.roidictionary as roidict

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
        
        # current H5 file path for ROI embedding
        self.current_h5_path = None

        #create a menu bar
        self.menu = qt.QMenuBar(self)
        self.menu.setNativeMenuBar(False)

        # add file menu for video/dataset upload (h5py for now only)
        file_menu = self.menu.addMenu("File")
        video_upload_action = qt.QAction("Video upload", self)
        dataset_upload_action = qt.QAction("H5 Dataset upload", self)
        self.clear_dataset_action = qt.QAction("Clear Dataset", self)
        self.clear_dataset_action.setEnabled(False)  # Disabled until dataset is loaded
        video_upload_action.triggered.connect(lambda : self._open_file("vid"))
        dataset_upload_action.triggered.connect(lambda : self._open_file("h5"))
        self.clear_dataset_action.triggered.connect(self._clear_dataset)
        if file_menu is not None:
            file_menu.addAction(video_upload_action)
            file_menu.addAction(dataset_upload_action)
            file_menu.addSeparator()
            file_menu.addAction(self.clear_dataset_action)

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
        self.camera_settings_action.setEnabled(False)  # Permanently disabled for now

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
            camera_menu.addSeparator()
            if self.camera_dshow_settings_action is not None:
                camera_menu.addAction(self.camera_dshow_settings_action)
            camera_menu.addAction(self.camera_settings_action)
            camera_menu.addSeparator()
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
        
        # Connect frame change signal to update current frame stats
        self.view.sigFrameChanged.connect(self._on_frame_changed)

        # create Dock widgets
        self._roisTabWidgetDockWidget = qt.QDockWidget(parent=self)
        self._roisTabWidgetDockWidget.setWidget(self._roisTabWidget)
        self.addDockWidget(qt.Qt.DockWidgetArea.RightDockWidgetArea, self._roisTabWidgetDockWidget)

        # create Dock widgets
        self._roiStatsWindowDockWidget = qt.QDockWidget(parent=self)
        self._roiStatsWindowDockWidget.setWidget(self._statsWidget)
        self.addDockWidget(qt.Qt.DockWidgetArea.RightDockWidgetArea, self._roiStatsWindowDockWidget)

        # Connect ROI signal to register ROI automatically
        self._regionManagerWidget.roiManager.sigRoiAdded.connect(self._on_roi_drawn)
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
            # Close any previous playback file first (so we can save ROIs)
            if self.playback is not None:
                try:
                    self.playback.close()
                except Exception:
                    pass
                self.playback = None
            
            # Save ROIs to current dataset before switching (if embed enabled)
            self._save_rois_before_switch()
            
            playback = H5Playback(file_path, file_type)
            
            # Check if user cancelled conversion
            if playback.cancelled:
                return
            
            image_dataset = getattr(playback, "image_dataset", None)
            dataset_size = getattr(playback, "dataset_size", 0)

            if image_dataset is None or dataset_size <= 0:
                qt.QMessageBox.warning(self, "Failed to load the media", "No frames found in the selected file.")
                return

            # Store playback for cleanup
            self.playback = playback
            
            # Get the actual H5 file path (may be different for video conversions)
            if hasattr(playback, 'h5_file') and playback.h5_file is not None:
                self.current_h5_path = playback.h5_file.filename
            else:
                self.current_h5_path = None
            
            print(f"Loaded dataset with shape {image_dataset.shape} from {file_path}")
            print(image_dataset)
            self.view.setStack(image_dataset)
            self.view.setFrameNumber(0)
            
            # Update stats widget with new dataset
            self._statsWidget.setDataset(image_dataset)
            
            # Show browser controls when dataset is loaded
            self.view._browser.setVisible(True)
            self.view._browser_label.setVisible(True)
            # Enable clear dataset action
            self.clear_dataset_action.setEnabled(True)
            
            # Handle ROI loading from H5
            self._handle_roi_loading()
            
        except Exception as e:
            qt.QMessageBox.warning(self, "Failed to load the media", f"Failed to load HDF5 dataset or convert video file to HDF5: {e}")

    def _clear_dataset(self):
        """Clear the current dataset from the StackView and reset to clean state."""
        # Capture ROI data BEFORE clearing stack (clearing removes ROIs)
        h5_path_to_save = self.current_h5_path
        captured_rois = list(self._regionManagerWidget.getRois())
        captured_embed_enabled = self._regionManagerWidget.isEmbedChecked()
        
        # Clear the StackView (releases dataset reference, removes ROIs)
        self.view.setStack(None)
        
        # Update stats widget to clear dataset
        self._statsWidget.setDataset(None)
        
        # Close any open playback file (must be closed before we can write ROIs)
        if self.playback is not None:
            try:
                self.playback.close()
            except Exception:
                pass
            self.playback = None
        
        # Now save ROIs using captured data (file is closed and can be reopened in r+ mode)
        if h5_path_to_save is not None:
            self._save_rois_to_current_h5(rois=captured_rois, embed_enabled=captured_embed_enabled, h5_path=h5_path_to_save)
        
        # Clear current H5 path
        self.current_h5_path = None
        
        # Hide browser controls
        self._set_browse_controls_visible(False)
        
        # Disable clear action and embed checkbox
        self.clear_dataset_action.setEnabled(False)
        self._regionManagerWidget.setEmbedEnabled(False)
        
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
        # Save ROIs before stopping camera if recording was active
        if self.camera is not None and self.camera.is_recording:
            self._save_rois_to_current_h5()
        
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
        
        # Clear current H5 path and disable embed
        self.current_h5_path = None
        if hasattr(self, '_regionManagerWidget') and self._regionManagerWidget is not None:
            self._regionManagerWidget.setEmbedEnabled(False)

    def _camera_init(self, port, backend, name, fps):
        try:
            # Stop any existing camera/session before reinitializing
            self._stop_camera()
            print(f"Initializing camera on port {port} with backend {backend} and name {name}")
            self.camera = CameraInit(500, port, backend, name, fps)

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
                
                # Update stats widget with live frame dataset
                self._statsWidget.setDataset(self.camera.latest_frame)

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
        # self.camera_settings_action is permanently disabled
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
        self._recording_last_frame_count = 0  # Track frame count for browser updates
        self._recording_dataset_bound = False  # Track if we've bound the dataset
        self.current_h5_path = file_path  # Track for ROI embedding
        
        # Update stats widget with recording dataset (will be set properly in camera loop)
        # For now, just notify that we're starting recording
        
        # Show browser controls for navigating recorded frames (but don't bind dataset yet - wait for first frame)
        self._set_browse_controls_visible(True)
        # Check sync by default so user sees live recording
        if self.syncButton is not None:
            self.syncButton.setChecked(True)
        
        # Enable ROI embedding (auto-checked for new recordings)
        self._regionManagerWidget.setEmbedEnabled(True, checked=True)
        
        # Update menu state
        self.start_recording_action.setEnabled(False)
        self.stop_recording_action.setEnabled(True)

    def _stop_recording(self):
        """Stop recording and switch back to live preview mode."""
        if self.camera is None:
            return
        
        # Save ROIs to recording before stopping (if embed enabled)
        self._save_rois_to_current_h5()
        
        # Clear StackView before stopping to prevent access to closed dataset
        self.view.setStack(None)
        
        # Reset recording tracking state
        self._recording_dataset_bound = False
        self._recording_last_frame_count = 0
        
        file_path = self.camera.stop_recording()
        
        # Clear current H5 path and disable embed
        self.current_h5_path = None
        self._regionManagerWidget.setEmbedEnabled(False)
        
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
                frame_count = self.camera.frame_index
                
                if frame_count > 0:
                    # Bind dataset on first frame or after resize
                    current_stack = self.view.getStack(copy=False, returnNumpyArray=False)
                    needs_rebind = (not getattr(self, '_recording_dataset_bound', False) or 
                                   current_stack is None or 
                                   current_stack[0] is not self.camera.image_dataset)
                    
                    if needs_rebind:
                        # Preserve current frame position when rebinding
                        current_frame = self.view.getFrameNumber() if self._recording_dataset_bound else 0
                        self.view.setStack(self.camera.image_dataset)
                        self._recording_dataset_bound = True
                        
                        # Update stats widget with recording dataset
                        self._statsWidget.setDataset(self.camera.image_dataset)
                        
                        # Set initial range
                        self.view._browser.setRange(0, frame_count - 1)
                        # Restore frame position (clamped to valid range)
                        restored_frame = min(current_frame, frame_count - 1)
                        self.view.setFrameNumber(restored_frame)
                    
                    # Update browser range only when frame count changes
                    last_count = getattr(self, '_recording_last_frame_count', 0)
                    if frame_count != last_count:
                        # Save current position before updating range
                        current_pos = self.view.getFrameNumber()
                        self.view._browser.setRange(0, frame_count - 1)
                        # Restore position if not syncing
                        if self.syncButton is None or not self.syncButton.isChecked():
                            # Keep user's position, clamped to valid range
                            self.view.setFrameNumber(min(current_pos, frame_count - 1))
                        self._recording_last_frame_count = frame_count
                    
                    # Auto-sync to latest frame if sync button is checked
                    if self.syncButton is not None and self.syncButton.isChecked():
                        self.view.setFrameNumber(frame_count - 1)
            else:
                # Live preview mode: update the plot with latest frame
                if self.camera.latest_frame is not None:
                    frame = self.camera.latest_frame[0] if self.camera.latest_frame.ndim == 3 else self.camera.latest_frame
                    self.current_frame = frame
                    self.plot.addImage(self.current_frame, replace=True, resetzoom=False)
                    
                    # Update stats widget with current live frame
                    self._statsWidget.updateCurrentFrame(0, frame)
    
    def _on_frame_changed(self, frame_index):
        """Handle frame change in StackView - update stats for new frame."""
        # Get current frame data from view
        stack = self.view.getStack(copy=False, returnNumpyArray=False)
        
        if stack is not None and len(stack) > frame_index:
            try:
                if hasattr(stack, '__getitem__'):
                    frame_data = stack[frame_index]
                else:
                    frame_data = None
                
                # Update stats widget
                self._statsWidget.updateCurrentFrame(frame_index, frame_data)
            except Exception as e:
                print(f"Error updating frame stats: {e}")
    
    def _on_roi_drawn(self, roi):
        """
        Handle when a new ROI is drawn.
        In the new system, ROIs are not automatically added to stats.
        Just register it as available.
        
        Args:
            roi: The newly drawn ROI object
        """
        # Don't automatically add to stats (prevents freezing)
        # User must use the + button to add ROI to analysis
        pass
            
    def _about_menu(self):
        aw = AboutWindow(self)
        aw.show()

    def update_dataset(self, plot, dataset):
        """Update the plot with the new dataset"""
        framenum = plot.getFrameNumber()
        plot.setStack(dataset)
        plot.setFrameNumber(framenum)

    def _save_rois_to_current_h5(self, rois=None, embed_enabled=None, h5_path=None):
        """Save ROIs to the current H5 file if embed is enabled.
        
        Args:
            rois: Optional pre-captured list of ROIs (use if stack may be cleared before save)
            embed_enabled: Optional pre-captured embed checkbox state
            h5_path: Optional H5 path to save to (overrides current_h5_path)
        """
        # Use provided values or get current values
        if embed_enabled is None:
            embed_enabled = self._regionManagerWidget.isEmbedChecked()
        if not embed_enabled:
            return
        
        save_path = h5_path if h5_path is not None else self.current_h5_path
        if save_path is None:
            return
        
        # Check if file is writable
        if not roidict.h5_is_writable(save_path):
            qt.QMessageBox.warning(self, "Read-Only Dataset",
                "This dataset is read-only. ROIs cannot be embedded.\n\n"
                "Please save ROIs manually using the Save button in the ROI panel.")
            return
        
        # Use provided ROIs or get current ROIs
        if rois is None:
            rois = self._regionManagerWidget.getRois()
        print(f"DEBUG _save_rois_to_current_h5: Saving {len(rois)} ROIs to {save_path}")
        
        # Warn if saving empty ROI set
        if len(rois) == 0:
            reply = qt.QMessageBox.question(self, "Save Empty ROIs?",
                "There are no ROIs to save. This will clear any previously saved ROIs in the dataset.\n\n"
                "Do you want to continue?",
                qt.QMessageBox.Yes | qt.QMessageBox.No,
                qt.QMessageBox.No)
            if reply != qt.QMessageBox.Yes:
                return
        
        success = roidict.save_rois_to_h5(rois, save_path, embed_enabled=embed_enabled)
        if success:
            print(f"Saved {len(rois)} ROIs to {self.current_h5_path}")
        else:
            qt.QMessageBox.warning(self, "Save Failed",
                "Failed to save ROIs to the dataset. Please save manually using the Save button.")

    def _save_rois_before_switch(self):
        """Prompt user to save ROIs before switching datasets."""
        if not self._regionManagerWidget.isEmbedChecked():
            return
        
        if self.current_h5_path is None:
            return
        
        if not self._regionManagerWidget.hasRois():
            return  # Nothing to save
        
        reply = qt.QMessageBox.question(self, "Save ROIs?",
            "Do you want to save ROIs to the current dataset before switching?\n\n"
            "Click 'No' to discard ROI changes.",
            qt.QMessageBox.Yes | qt.QMessageBox.No,
            qt.QMessageBox.Yes)
        
        if reply == qt.QMessageBox.Yes:
            self._save_rois_to_current_h5()

    def _handle_roi_loading(self):
        """Handle loading ROIs when opening an H5 file."""
        if self.current_h5_path is None:
            # Enable embed for new video conversions
            self._regionManagerWidget.setEmbedEnabled(True, checked=True)
            return
        
        # Check if H5 has saved ROIs
        if not roidict.h5_has_rois(self.current_h5_path):
            # No ROIs in file, just enable embed
            self._regionManagerWidget.setEmbedEnabled(True, checked=True)
            return
        
        # Load ROIs from file
        saved_rois, embed_enabled = roidict.load_rois_from_h5(self.current_h5_path, plot=self.plot)
        
        if saved_rois is None:
            self._regionManagerWidget.setEmbedEnabled(True, checked=True)
            return
        
        # Check if there are existing ROIs
        if self._regionManagerWidget.hasRois():
            # Show dialog to choose action
            dialog = qt.QMessageBox(self)
            dialog.setWindowTitle("ROIs Found in Dataset")
            dialog.setText("This dataset contains saved ROIs, but you also have ROIs currently drawn.")
            dialog.setInformativeText("What would you like to do?")
            
            load_btn = dialog.addButton("Load from dataset (discard current)", qt.QMessageBox.AcceptRole)
            keep_btn = dialog.addButton("Keep current ROIs", qt.QMessageBox.RejectRole)
            dialog.setDefaultButton(load_btn)
            
            dialog.exec()
            
            if dialog.clickedButton() == load_btn:
                self._regionManagerWidget.loadROIsFromList(saved_rois)
                print(f"Loaded {len(saved_rois)} ROIs from dataset")
            else:
                print("Kept current ROIs, discarding saved ROIs from dataset")
        else:
            # No current ROIs, just load from file
            self._regionManagerWidget.loadROIsFromList(saved_rois)
            print(f"Loaded {len(saved_rois)} ROIs from dataset")
        
        # Enable embed with saved state
        self._regionManagerWidget.setEmbedEnabled(True, checked=embed_enabled)

    def closeEvent(self, event):
        """Ensure camera resources are released on window close."""
        # Capture ROI data BEFORE any cleanup (cleanup clears ROIs)
        h5_path_to_save = self.current_h5_path
        captured_rois = list(self._regionManagerWidget.getRois())
        captured_embed_enabled = self._regionManagerWidget.isEmbedChecked()
        
        # Close playback file first so we can save ROIs
        if self.playback is not None:
            try:
                self.playback.close()
            except Exception:
                pass
            self.playback = None
        
        # Save ROIs using captured data before cleanup clears them
        if h5_path_to_save is not None:
            self._save_rois_to_current_h5(rois=captured_rois, embed_enabled=captured_embed_enabled, h5_path=h5_path_to_save)
        
        # Cleanup stats widget (stop computation engine)
        if hasattr(self, '_statsWidget'):
            self._statsWidget.cleanup()
        
        self._stop_camera()
        super().closeEvent(event)

def main():
    app = qt.QApplication([])
    window = _RoiStatsDisplayExWindow()
    window.show()
    app.exec()

if __name__ == "__main__":
    main()