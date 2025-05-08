import sys
import mido
import threading
import time
import numpy as np
import pyqtgraph as pg

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QSpinBox, QComboBox, QPushButton, QStackedWidget, QLabel
)
from PyQt5.QtCore import Qt


class MidiTool(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MIDI Tool with ADSR and ARP")
        self.setGeometry(100, 100, 800, 600)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Toggle button to switch views
        self.toggle_view_button = QPushButton("Switch to Note Hold View")
        self.toggle_view_button.setCheckable(True)
        self.toggle_view_button.toggled.connect(self.toggle_view)
        layout.addWidget(self.toggle_view_button)

        # Stacked widget to switch between ADSR and Note Hold views
        self.stacked_widget = QStackedWidget()
        layout.addWidget(self.stacked_widget)

        # ADSR view
        self.adsr_view = QWidget()
        adsr_layout = QVBoxLayout()
        self.adsr_view.setLayout(adsr_layout)

        # Plot widget
        self.plot_widget = pg.PlotWidget()
        adsr_layout.addWidget(self.plot_widget)

        # Controls for ADSR
        self.attack_input = QSpinBox()
        self.attack_input.setValue(1000)
        self.attack_input.valueChanged.connect(self.update_graph)
        adsr_layout.addWidget(QLabel("Attack (ms)"))
        adsr_layout.addWidget(self.attack_input)

        self.decay_input = QSpinBox()
        self.decay_input.setValue(500)
        self.decay_input.valueChanged.connect(self.update_graph)
        adsr_layout.addWidget(QLabel("Decay (ms)"))
        adsr_layout.addWidget(self.decay_input)

        self.sustain_input = QSpinBox()
        self.sustain_input.setValue(60)
        self.sustain_input.valueChanged.connect(self.update_graph)
        adsr_layout.addWidget(QLabel("Sustain (%)"))
        adsr_layout.addWidget(self.sustain_input)

        self.release_input = QSpinBox()
        self.release_input.setValue(1500)
        self.release_input.valueChanged.connect(self.update_graph)
        adsr_layout.addWidget(QLabel("Release (ms)"))
        adsr_layout.addWidget(self.release_input)

        # ARP controls
        self.arp_direction_dropdown = QComboBox()
        self.arp_direction_dropdown.addItems(["Up", "Down", "Up-Down"])
        adsr_layout.addWidget(QLabel("ARP Direction"))
        adsr_layout.addWidget(self.arp_direction_dropdown)

        self.octave_range_input = QSpinBox()
        self.octave_range_input.setValue(1)
        adsr_layout.addWidget(QLabel("Octave Range"))
        adsr_layout.addWidget(self.octave_range_input)

        # Add ADSR view to stacked widget
        self.stacked_widget.addWidget(self.adsr_view)

        # Note Hold view
        self.note_hold_view = QWidget()
        hold_layout = QVBoxLayout()
        self.note_hold_view.setLayout(hold_layout)

        self.hold_button = QPushButton("Toggle Note On/Off")
        self.hold_button.setCheckable(True)
        self.hold_button.toggled.connect(self.toggle_note)
        hold_layout.addWidget(self.hold_button)

        # Add Note Hold view to stacked widget
        self.stacked_widget.addWidget(self.note_hold_view)

        self.update_graph()

    def toggle_view(self, checked):
        if checked:
            self.stacked_widget.setCurrentIndex(1)
            self.toggle_view_button.setText("Switch to ADSR View")
        else:
            self.stacked_widget.setCurrentIndex(0)
            self.toggle_view_button.setText("Switch to Note Hold View")

    def update_graph(self):
        a = self.attack_input.value() / 1000.0
        d = self.decay_input.value() / 1000.0
        s = self.sustain_input.value() / 100.0
        r = self.release_input.value() / 1000.0

        t = np.linspace(0, a + d + r, 500)
        y = []

        for x in t:
            if x < a:
                y.append(x / a)
            elif x < a + d:
                y.append(1 - (1 - s) * ((x - a) / d))
            elif x < a + d + r:
                y.append(s * (1 - ((x - a - d) / r)))
            else:
                y.append(0)

        self.plot_widget.clear()
        self.plot_widget.plot(t, y, pen='g')

    def toggle_note(self, is_on):
        try:
            port_name = mido.get_output_names()[0]
            with mido.open_output(port_name) as outport:
                note = 61  # C#4
                if is_on:
                    outport.send(mido.Message('note_on', note=note, velocity=100, channel=0))
                else:
                    outport.send(mido.Message('note_off', note=note, velocity=100, channel=0))
        except Exception as e:
            print("MIDI Error:", e)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MidiTool()
    window.show()
    sys.exit(app.exec_())
