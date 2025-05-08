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
        self.setWindowTitle("MIDI Tool with ADSR and Note Hold")
        self.setGeometry(100, 100, 800, 600)

        # Central layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # View toggle
        self.toggle_view_button = QPushButton("Switch to Note Hold View")
        self.toggle_view_button.setCheckable(True)
        self.toggle_view_button.toggled.connect(self.toggle_view)
        layout.addWidget(self.toggle_view_button)

        # Stack views
        self.stacked_widget = QStackedWidget()
        layout.addWidget(self.stacked_widget)

        # --- ADSR View ---
        self.adsr_view = QWidget()
        adsr_layout = QVBoxLayout()
        self.adsr_view.setLayout(adsr_layout)

        self.plot_widget = pg.PlotWidget()
        adsr_layout.addWidget(self.plot_widget)

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

        self.arp_direction_dropdown = QComboBox()
        self.arp_direction_dropdown.addItems(["Up", "Down", "Up-Down"])
        adsr_layout.addWidget(QLabel("ARP Direction"))
        adsr_layout.addWidget(self.arp_direction_dropdown)

        self.octave_range_input = QSpinBox()
        self.octave_range_input.setValue(1)
        adsr_layout.addWidget(QLabel("Octave Range"))
        adsr_layout.addWidget(self.octave_range_input)

        self.stacked_widget.addWidget(self.adsr_view)
        self.update_graph()

        # --- Note Hold View ---
        self.note_hold_view = QWidget()
        hold_layout = QVBoxLayout()
        self.note_hold_view.setLayout(hold_layout)

        self.hold_button = QPushButton("Toggle Note On/Off")
        self.hold_button.setCheckable(True)
        self.hold_button.toggled.connect(self.toggle_note)
        hold_layout.addWidget(self.hold_button)

        self.midi_note_input = QSpinBox()
        self.midi_note_input.setRange(0, 127)
        self.midi_note_input.setValue(61)
        hold_layout.addWidget(QLabel("MIDI Note (0–127)"))
        hold_layout.addWidget(self.midi_note_input)

        self.velocity_input = QSpinBox()
        self.velocity_input.setRange(1, 127)
        self.velocity_input.setValue(100)
        hold_layout.addWidget(QLabel("Velocity (1–127)"))
        hold_layout.addWidget(self.velocity_input)

        self.bpm_input = QSpinBox()
        self.bpm_input.setRange(20, 300)
        self.bpm_input.setValue(60)
        hold_layout.addWidget(QLabel("BPM"))
        hold_layout.addWidget(self.bpm_input)

        self.note_duration_input = QSpinBox()
        self.note_duration_input.setRange(1, 16)
        self.note_duration_input.setValue(1)
        hold_layout.addWidget(QLabel("Note Duration (beats)"))
        hold_layout.addWidget(self.note_duration_input)

        self.bars_input = QSpinBox()
        self.bars_input.setRange(1, 64)
        self.bars_input.setValue(4)
        hold_layout.addWidget(QLabel("Number of Bars"))
        hold_layout.addWidget(self.bars_input)

        self.stacked_widget.addWidget(self.note_hold_view)

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
        if is_on:
            self.hold_thread = threading.Thread(target=self.play_note_loop)
            self.hold_thread.daemon = True
            self.hold_thread.start()
        else:
            self.stop_requested = True

    def play_note_loop(self):
        try:
            port_name = mido.get_output_names()[0]
            base_note = self.midi_note_input.value()
            velocity = self.velocity_input.value()
            bpm = self.bpm_input.value()
            duration_beats = self.note_duration_input.value()
            bars = self.bars_input.value()
            beat_duration = 60.0 / bpm
            note_duration_sec = duration_beats * beat_duration
            total_beats = bars * 4

            # ARP config
            direction = self.arp_direction_dropdown.currentText().lower()
            octave_range = self.octave_range_input.value()

            # Build note sequence
            arp_notes = []
            for octv in range(octave_range):
                arp_notes.append(base_note + 12 * octv)
            if direction == "down":
                arp_notes = sorted(arp_notes, reverse=True)
            elif direction == "up-down":
                arp_notes = arp_notes + arp_notes[::-1][1:-1]

            self.stop_requested = False
            beat_count = 0

            with mido.open_output(port_name) as outport:
                while not self.stop_requested and beat_count < total_beats:
                    for note in arp_notes:
                        if self.stop_requested or beat_count >= total_beats:
                            break
                        outport.send(mido.Message('note_on', note=note, velocity=velocity, channel=0))
                        time.sleep(note_duration_sec * 0.9)
                        outport.send(mido.Message('note_off', note=note, velocity=velocity, channel=0))
                        time.sleep(note_duration_sec * 0.1)
                        beat_count += duration_beats

            self.hold_button.setChecked(False)

        except Exception as e:
            print("MIDI Error:", e)



if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MidiTool()
    window.show()
    sys.exit(app.exec_())
