import silx.gui.qt as qt
import os
import cv2.videoio_registry as cv2_reg
import camera.opencv_capture as cap
import cv2_enumerate_cameras as cv2_enum

class CameraConnectWindow(qt.QMainWindow):
    """Window for setting up and launching the camera."""
    backendValuePicked = qt.Signal(int, int, str)

    def __init__(self):
        super().__init__()

        cv2_enum.supported_backends

        # Force the window not to fullscreen
        self.setWindowTitle("Camera Setup and Launch")
        self.resize(400, 200)

        self.centralWidget = qt.QWidget(self)
        self.setCentralWidget(self.centralWidget)

        self.vlayout = qt.QVBoxLayout(self.centralWidget)

        self.hlayout = qt.QHBoxLayout()
        self.vlayout.addLayout(self.hlayout)

        self.hlayout.addWidget(qt.QLabel("Backend: ", self))
        self.backend_combo = qt.QComboBox(self)
        for backend in cv2_enum.supported_backends:
            self.backend_combo.addItem(cv2_reg.getBackendName(backend))
        self.hlayout.addWidget(self.backend_combo)
        self.backend_combo.currentIndexChanged.connect(self.refresh_camera_list)

        self.list_widget = qt.QListWidget(self)
        self.vlayout.addWidget(self.list_widget)

        self.refresh_button = qt.QPushButton("Refresh Camera List", self)
        self.refresh_button.clicked.connect(self.refresh_camera_list)
        self.vlayout.addWidget(self.refresh_button)
        self.refresh_camera_list()

        # Create a button to save the updated config values
        save_button = qt.QPushButton("Save and Launch Camera", self)
        save_button.clicked.connect(self._save_and_launch_camera)
        self.vlayout.addWidget(save_button)

    def _save_and_launch_camera(self):
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            qt.QMessageBox.warning(self, "No Selection", "Please select a camera from the list.")
            return

        selected_text = selected_items[0].text()
        port_str = selected_text.split(":")[0].strip().split(" ")[1]
        port = int(port_str)
        backend = cv2_enum.supported_backends[self.backend_combo.currentIndex()]
        name = cv2_reg.getBackendName(backend)

        # Emit the signal with the selected port and backend
        self.backendValuePicked.emit(port, backend, name)
        self.close()

    def refresh_camera_list(self):
        self.list_widget.clear()
        print(cv2_enum.supported_backends)
        print(cv2_enum.enumerate_cameras())
        camera_ports = cv2_enum.enumerate_cameras(cv2_enum.supported_backends[self.backend_combo.currentIndex()])
        for port in camera_ports:
            item = qt.QListWidgetItem(f"Port {port}:")
            self.list_widget.addItem(item)
