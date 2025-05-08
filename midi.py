import sys
import mido
import threading
import time
import numpy as np
import pyqtgraph as pg

from PyQt5.QtWidgets import (
    QApplication, QHBoxLayout, QMainWindow, QSlider, QWidget, QVBoxLayout,
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
        self.plot_widget.showAxis('bottom', False)
        self.plot_widget.showAxis('left', False)
        self.plot_widget.setBackground('#111')  # optional dark background
        self.plot_widget.setMouseEnabled(x=False, y=False)
        self.plot_widget.setMenuEnabled(False)
        self.plot_widget.setContentsMargins(0, 0, 0, 0)
        self.plot_widget.plotItem.vb.suggestPadding(0)

        adsr_layout.addWidget(self.plot_widget)

        # Slider layout
        slider_layout = QHBoxLayout()
        slider_wrapper = QWidget()
        slider_wrapper.setMinimumHeight(150)  # Adjust this as needed
        slider_wrapper.setLayout(slider_layout)
        adsr_layout.addWidget(slider_wrapper)

        # Attack slider
        self.attack_slider = QSlider(Qt.Vertical)
        self.attack_slider.setRange(0, 5000)
        self.attack_slider.setValue(1000)
        self.attack_slider.valueChanged.connect(self.update_graph)
        self.style_slider(self.attack_slider, "#ff6600")  # orange for attack
        slider_layout.addWidget(self._labeled_slider("Attack (ms)", self.attack_slider))

        # Decay slider
        self.decay_slider = QSlider(Qt.Vertical)
        self.decay_slider.setRange(0, 5000)
        self.decay_slider.setValue(500)
        self.decay_slider.valueChanged.connect(self.update_graph)
        self.style_slider(self.decay_slider, "#ffaa00")
        slider_layout.addWidget(self._labeled_slider("Decay (ms)", self.decay_slider))

        # Sustain slider
        self.sustain_slider = QSlider(Qt.Vertical)
        self.sustain_slider.setRange(0, 100)
        self.sustain_slider.setValue(60)
        self.sustain_slider.valueChanged.connect(self.update_graph)
        self.style_slider(self.sustain_slider, "#33ccff")
        slider_layout.addWidget(self._labeled_slider("Sustain (%)", self.sustain_slider))

        # Release slider
        self.release_slider = QSlider(Qt.Vertical)
        self.release_slider.setRange(0, 5000)
        self.release_slider.setValue(1500)
        self.release_slider.valueChanged.connect(self.update_graph)
        self.style_slider(self.release_slider, "#cc33ff")
        slider_layout.addWidget(self._labeled_slider("Release (ms)", self.release_slider))

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
        a = self.attack_slider.value() / 1000.0
        d = self.decay_slider.value() / 1000.0
        s = self.sustain_slider.value() / 100.0
        r = self.release_slider.value() / 1000.0

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

    def _labeled_slider(self, label_text, slider):
        wrapper = QWidget()
        v_layout = QVBoxLayout()
        v_layout.addWidget(QLabel(label_text, alignment=Qt.AlignCenter))
        v_layout.addWidget(slider)
        wrapper.setLayout(v_layout)
        return wrapper

    def style_slider(self, slider, color="#00cc66"):
        slider.setStyleSheet(f"""
            QSlider::groove:vertical {{
                border: 1px solid #444;
                background: #222;
                width: 8px;
                border-radius: 4px;
            }}
            QSlider::handle:vertical {{
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 {color}, stop: 1 #000
                );
                border: 1px solid #111;
                height: 20px;
                margin: -4px;
                border-radius: 6px;
            }}
        """)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MidiTool()
    window.show()
    sys.exit(app.exec_())
