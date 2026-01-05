import cv2
import cv2.videoio_registry as cv2_reg
import os
import numpy
import h5py
import datetime
import silx.gui.qt as qt
from typing import Callable, Any

class CameraInit:
    """Class for capturing frames from a camera. Supports live display and optional HDF5 recording."""
    def __init__(self, initial_size, port=1, backend=cv2.CAP_ANY, name="Camera Placeholder", fps=1.0):
        try:
            self.frame_index = 0
            self.fps = float(fps)
            self.dataset_size = initial_size
            self.image_dataset = None  # HDF5 dataset (only created when recording)
            self.latest_frame = None  # Single-frame buffer for live display
            self.camera_port = port
            self.camera_backend = backend
            self.camera_name = name
            self.on_resize: Callable[[Any], None] | None = None
            self.h5_file = None  # HDF5 file handle
            self.is_recording = False  # Recording state
            
            # Callback for resizing the dataset
            self.cache_folder = "cacheimg"
            os.makedirs(self.cache_folder, exist_ok=True)
            
            # Open the camera
            self.cap = cv2.VideoCapture(self.camera_port, self.camera_backend)
            self.cap.set(cv2.CAP_PROP_FPS, self.fps)
            # Reduce internal buffer to minimize frame delay
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            print(f"Camera FPS: {self.cap.get(cv2.CAP_PROP_FPS)} CV2 FPS set to {self.fps}")
            if not self.cap.isOpened():
                qt.QMessageBox.warning(None, "Camera Error", "Failed to open camera. Check if it is connected."+
            "Check the Camera connection"+
                                    " menu for more information.")
                return

            # Initialize single-frame buffer for live display (no HDF5 yet)
            gray_frame = self._capture_frame_raw()
            if gray_frame is None:
                qt.QMessageBox.critical(None, "Camera Initialization Error", "Failed to capture initial frame from camera.")
                return
            height, width = gray_frame.shape

            self.latest_frame = numpy.array(numpy.zeros((1, height, width)), dtype=numpy.float32)
            self.latest_frame[0] = gray_frame
            #self.latest_frame = numpy.array([self._capture_frame_raw], dtype=numpy.float32)
            self.frame_shape = self.latest_frame.shape[1:]  # (height, width)

        except Exception as e:
            qt.QMessageBox.critical(None, "Camera Initialization Error", f"An error occurred during camera initialization: {str(e)}")

    def capture_frame(self):
        """ Capture a frame from the camera. Store in HDF5 if recording, otherwise in circular buffer. """
        nfr = self._capture_frame_raw()
        if nfr is None:
            return None
        
        if self.is_recording and self.image_dataset is not None:
            # Store in HDF5 dataset
            if self.frame_index >= self.dataset_size:
                new_size = int(self.dataset_size + 500)
                print(f"Resizing dataset from {self.dataset_size} to {new_size} frames...")
                self.image_dataset.resize(new_size, axis=0)
                self.dataset_size = new_size
                if self.on_resize is not None:
                    self.on_resize(self.image_dataset)
            self.image_dataset[self.frame_index] = nfr
            self.frame_index += 1
        else:
            # Store only the latest frame for live display
            print("Storing latest frame for live display")
            print(nfr)
            if self.latest_frame is not None:
                self.latest_frame[0] = nfr

    def _capture_frame_raw(self):
        """ Capture a raw frame from the camera and return it as a numpy array. """
        # Flush all buffered frames by grabbing until we get the latest one
        for _ in range(10):  # Flush up to 10 buffered frames
            grabbed = self.cap.grab()
            if not grabbed:
                break
        
        ret, frame = self.cap.retrieve()
        if not ret:
            print("Failed to capture frame from camera.")
            return None
        
        # Convert to grayscale
        nfr = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return nfr

    def start_recording(self, file_path=None):
        """ Initialize HDF5 recording. Must be called before capturing frames to record.
        
        Args:
            file_path: Optional custom file path for the HDF5 file. If None, uses default naming.
        """
        if self.is_recording:
            return  # Already recording
        
        if self.latest_frame is None:
            print("Error: No frame captured yet; cannot start recording.")
            return
        
        height, width = self.frame_shape
        
        # Use provided path or generate default
        if file_path is None:
            file_path = os.path.join(self.cache_folder, f"dataset_{datetime.datetime.now().strftime('%d-%m-%Y_%H-%M-%S')}.h5")
        
        self.h5_file = h5py.File(file_path, "w")
        self.image_dataset = self.h5_file.create_dataset(
            "arrays",
            shape=(self.dataset_size, height, width),
            maxshape=(None, height, width),
            dtype=numpy.float32,
            chunks=(10, height, width),
            compression='gzip',
        )
        self.is_recording = True
        self.frame_index = 0
        self.recording_file_path = file_path
        print(f"Started HDF5 recording to {self.h5_file.filename}")

    def stop_recording(self):
        """ Stop HDF5 recording and close the file. Returns the file path of the recording. """
        if not self.is_recording:
            return None
        
        self.is_recording = False
        file_path = getattr(self, 'recording_file_path', None)
        if self.h5_file is not None:
            # Trim dataset to actual recorded frames
            if self.image_dataset is not None and self.frame_index < self.dataset_size:
                self.image_dataset.resize(self.frame_index, axis=0)
            self.h5_file.close()
            self.h5_file = None
        self.image_dataset = None
        recorded_frames = self.frame_index
        self.frame_index = 0
        print(f"Stopped HDF5 recording. Recorded {recorded_frames} frames to {file_path}")
        return file_path
    
    def get_default_recording_path(self):
        """ Returns the default file path for a new recording. """
        return os.path.join(self.cache_folder, f"dataset_{datetime.datetime.now().strftime('%d-%m-%Y_%H-%M-%S')}.h5")

    def cleanup(self):
        self.cap.release()
        if self.h5_file is not None:
            self.h5_file.close()
            self.h5_file = None

    def getFPS(self):
        """ Returns the FPS setting of the camera. """
        return self.fps
    
    def setFPS(self, fps: float):
        """ Sets the FPS of the camera. """
        self.cap.set(cv2.CAP_PROP_FPS, fps)
        self.fps = fps
 
    def getCurrentFrame(self):
        """ Returns the current frame index. """
        return (self.frame_index-2)
    
    def getBackend(self):
        """ Returns the backend used by OpenCV for this camera. """
        return cv2_reg.getBackendName(self.camera_backend)
    
    def openDSHOWSettings(self):
        """ Opens the DirectShow settings dialog for the camera (Windows only). """
        if os.name == 'nt':  # Check if the OS is Windows
            self.cap.set(cv2.CAP_PROP_SETTINGS, 1)
