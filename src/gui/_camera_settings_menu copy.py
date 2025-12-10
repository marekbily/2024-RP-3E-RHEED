import silx.gui.qt as qt
import os

class CameraSettingsWindowCopy(qt.QMainWindow):
    """Window for setting up and launching the camera."""
    buttonClicked = qt.Signal()

    def __init__(self):
        super().__init__()

        # Force the window not to fullscreen
        self.setWindowFlags(qt.Qt.WindowType.Tool)
        self.setWindowTitle("Camera Setup and Launch")
        self.resize(600, 400)

        self.input_fields = {}

        # Check if the camera_config.txt file is empty or non-existent, if yes create it with default values
        if not os.path.exists("camera_config.txt") or not os.path.getsize("camera_config.txt") > 0:
            with open("camera_config.txt", "w") as f:
                f.write(f"{0}\n")
                f.write(f"{10}\n")
                f.write(f"{1}\n")
                f.write(f"{0}\n")
                f.write(f"{0}\n")
                f.write(f"{0}\n")
                f.write(f"{0}\n")
                f.write(f"{0}\n")
                f.write(f"{0}\n")
                f.write(f"{0}\n")
                f.write(f"{0}\n")
                f.write(f"{0}\n")
                f.write(f"{0}\n")
                f.write(f"{0}\n")
                f.write(f"{0}\n")
                f.write(f"{0}\n")
                f.write(f"{0}\n")
                f.write(f"{0}\n")
                f.write(f"{0}\n")
                f.write(f"{0}\n")
                f.write(f"{0}\n")
                f.write(f"{0}\n")
                f.close()

        # Load the config values from the src/opencv_capture file
        self.config_values = self.load_config_values()

        # Create the main widget
        main_widget = qt.QWidget(self)
        self.setCentralWidget(main_widget)

        # Create layout
        layout = qt.QGridLayout()
        main_widget.setLayout(layout)

        # Create labels and input fields for each config value
        row = 0
        col = 0
        for field, value in self.config_values.items():
            label = qt.QLabel(field, self)
            layout.addWidget(label, row, col)

            input_field = qt.QLineEdit(str(value), self)
            self.input_fields[field] = input_field
            layout.addWidget(input_field, row, col+1)

            if col == 2:
                col = 0
                row += 1
            else:
                col += 2

        # Create a button to save the updated config values
        save_button = qt.QPushButton("Save and Launch Camera", self)
        save_button.clicked.connect(self.save_config_values)
        layout.addWidget(save_button, row, col)

    def load_config_values(self):
        config_values = {}
        with open('camera_config.txt', 'r') as f:
            config_values["Camera Port"] = int(f.readline())
            config_values["FPS"] = int(f.readline())
            config_values["Auto Exposure"] = int(f.readline())
            config_values["Exposure"] = int(f.readline())
            config_values["Gain"] = int(f.readline())
            config_values["Brightness"] = int(f.readline())
            config_values["Contrast"] = int(f.readline())
            config_values["Saturation"] = int(f.readline())
            config_values["Hue"] = int(f.readline())
            config_values["Sharpness"] = int(f.readline())
            config_values["Gamma"] = int(f.readline())
            config_values["White Balance Blue U"] = int(f.readline())
            config_values["Backlight"] = int(f.readline())
            config_values["Zoom"] = int(f.readline())
            config_values["Focus"] = int(f.readline())
            config_values["Autofocus"] = int(f.readline())
            config_values["WB Temperature"] = int(f.readline())
            config_values["FourCC"] = int(f.readline())
            config_values["Auto WB"] = int(f.readline())
            config_values["Temperature"] = int(f.readline())
            config_values["Trigger"] = int(f.readline())
            config_values["Trigger Delay"] = int(f.readline())
            f.close()

        return config_values
    
    def save_config_values(self):
        # save values from the text boxes into the config_values dictionary
        config_values = {}
        for field, input_field in self.input_fields.items():
            try:
                config_values[field] = int(input_field.text())
            except ValueError:
                qt.QMessageBox.warning(self, "Invalid Input", f"Field '{field}' must be an integer.")
                return

        # write the config_values dictionary into the camera_config.txt file
        with open('camera_config.txt', 'w') as f:
            f.truncate(0)
            for field, value in config_values.items():
                f.write(f"{value}\n")
            f.close()
        self.close()
        self.buttonClicked.emit()