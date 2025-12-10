import cv2
import os
import numpy
import h5py
import datetime
import silx.gui.qt as qt


class CameraInitTest:
    #testing of camera setting window
    def __init__(self):
        print("Initializing camera...")
        self.list_ports()

        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        self.cap.open(0)
        self.cap.set(cv2.CAP_PROP_SETTINGS, 1)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)

        app = qt.QApplication.instance()
        if app is None:
            app = qt.QApplication([])
        self.window = qt.QMainWindow()
        self.window.setWindowTitle("Camera Feed")
        self.label = qt.QLabel()
        self.window.setCentralWidget(self.label)
        self.window.show()
        self.timer = qt.QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30)
        self.window.show()
        self.window.destroyed.connect(self.close_camera)
    def close_camera(self):
        print("Closing camera...")
        if self.cap.isOpened():
            self.cap.release()
        cv2.destroyAllWindows()
    
if __name__ == "__main__":
    cam = CameraInit()
