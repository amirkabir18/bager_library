import sys
from PyQt6.QtWidgets import QApplication, QWidget, QPushButton, QLabel, QVBoxLayout

class MyWindow(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("My First PyQt5 App")
        self.resize(300, 150)
        self.label = QLabel("")
        self.button = QPushButton("Click Me")
        self.button.clicked.connect(self.show_message)

        layout = QVBoxLayout()
        layout.addWidget(self.button)
        layout.addWidget(self.label)
        self.setLayout(layout)

    def show_message(self):
        self.label.setText("You clicked me!")

app = QApplication(sys.argv)
window = MyWindow()
window.show()
sys.exit(app.exec())