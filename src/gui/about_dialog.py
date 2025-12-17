import silx.gui.qt as qt
import os

class AboutWindow(qt.QDialog):
    """About window with information about the app, contacts and links."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About")
        self.setFixedSize(850, 400)
        
        hlayout = qt.QHBoxLayout()
        hlayout.setContentsMargins(20, 20, 20, 20)
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "img", "logo.png")
        logo_label = qt.QLabel()
        logo_label.setPixmap(qt.QPixmap(icon_path).scaled(200, 200, qt.Qt.KeepAspectRatio, qt.Qt.SmoothTransformation))
        layout = qt.QVBoxLayout()
        hlayout.addLayout(layout)
        hlayout.addWidget(logo_label)
        
        gradient = qt.QLinearGradient(0, 0, 210, 0)
        gradient.setColorAt(0.0, qt.QColor("red"))
        gradient.setColorAt(0.2, qt.QColor("orange"))
        gradient.setColorAt(0.4, qt.QColor("yellow"))
        gradient.setColorAt(0.6, qt.QColor("green"))
        gradient.setColorAt(0.8, qt.QColor("blue"))
        gradient.setColorAt(1.0, qt.QColor("purple"))

        palette = qt.QPalette()
        palette.setBrush(qt.QPalette.WindowText, qt.QBrush(gradient))

        # App name and version
        app_name_label = qt.QLabel("2024-RP-3E-RHEED")
        app_name_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(app_name_label)
        
        version_label = qt.QLabel("Version 1.0")
        layout.addWidget(version_label)
        
        # Description
        description_label = qt.QLabel("This app is designed for real-time RHEED analysis for MBE and other epitaxy growth methods.")
        layout.addWidget(description_label)
        
        # Links
        links_label = qt.QLabel("Useful Links:")
        links_label.setStyleSheet("font-size: 14 px; font-weight: bold;")
        layout.addWidget(links_label)
        
        link1_label = qt.QLabel('<a href="https://github.com/gyarab/2024-RP-3E-RHEED/tree/main">Github</a>')
        link1_label.setOpenExternalLinks(True)
        layout.addWidget(link1_label)
        
        link2_label = qt.QLabel('<a href="https://github.com/silx-kit/silx">Silx library (Github)</a>')
        link2_label.setOpenExternalLinks(True)
        layout.addWidget(link2_label)
        
        # Contacts with Github links
        contacts_label = qt.QLabel("Contacts:")
        contacts_label.setStyleSheet("font-size: 14 px; font-weight: bold;")
        layout.addWidget(contacts_label)
        
        contact1_label = qt.QLabel("Marek Bílý - marek.bily@student.gyarab.cz")
        layout.addWidget(contact1_label)

        link3_label = qt.QLabel('<a href="https://github.com/marekbily">Github</a>')
        link3_label.setOpenExternalLinks(True)
        layout.addWidget(link3_label)
        
        contact2_label = qt.QLabel("Marek Švec - marek.svec@student.gyarab.cz")
        layout.addWidget(contact2_label)

        link4_label = qt.QLabel('<a href="https://github.com/mareksvec">Github</a>')
        link4_label.setOpenExternalLinks(True)
        layout.addWidget(link4_label)

        contact3_label = qt.QLabel("Jan Schreiber - jan.schreiber@student.gyarab.cz")
        layout.addWidget(contact3_label)

        link5_label = qt.QLabel('<a href="https://github.com/Schreiber-gyarab">Github</a>')
        link5_label.setOpenExternalLinks(True)
        layout.addWidget(link5_label)

       # Thanks to supervisors
        thanks_label = qt.QLabel("Special thanks to:") 
        thanks_label.setStyleSheet("font-size: 14 px; font-weight: bold;")
        layout.addWidget(thanks_label)

        thanks1_label = qt.QLabel("Dr. Dominik Kriegner")
        thanks1_label.setStyleSheet("font-weight: bold;")
        thanks1_label.setPalette(palette)
        layout.addWidget(thanks1_label)

        thanks2_label = qt.QLabel("Ing. Filip Křížek, Ph.D.")
        thanks2_label.setStyleSheet("font-weight: bold;")
        thanks2_label.setPalette(palette)
        layout.addWidget(thanks2_label)
        
        self.setLayout(hlayout)