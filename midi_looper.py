import sys
import time
import threading
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout,
    QLabel, QSpinBox, QFileDialog
)
from PyQt5.QtMultimedia import QSound
from mido import MidiFile, MidiTrack, Message, bpm2tempo
import mido
import rtmidi


class MidiLooper(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("MIDI Looper")
        self.bpm = 120
        self.recording = False
        self.playing = False
        self.overdubbing = False
        self.recorded_messages = []
        self.start_time = None

        self.init_ui()
        self.init_midi()

    def init_ui(self):
        layout = QVBoxLayout()

        self.bpm_label = QLabel("BPM:")
        self.bpm_spin = QSpinBox()
        self.bpm_spin.setRange(40, 300)
        self.bpm_spin.setValue(120)
        self.bpm_spin.valueChanged.connect(self.update_bpm)

        self.status = QLabel("Status: Idle")

        self.record_btn = QPushButton("Record")
        self.record_btn.clicked.connect(self.record)

        self.play_btn = QPushButton("Play")
        self.play_btn.clicked.connect(self.play)

        self.overdub_btn = QPushButton("Overdub")
        self.overdub_btn.clicked.connect(self.overdub)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self.stop)

        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self.save)

        layout.addWidget(self.bpm_label)
        layout.addWidget(self.bpm_spin)
        layout.addWidget(self.status)
        layout.addWidget(self.record_btn)
        layout.addWidget(self.play_btn)
        layout.addWidget(self.overdub_btn)
        layout.addWidget(self.stop_btn)
        layout.addWidget(self.save_btn)

        self.setLayout(layout)

    def update_bpm(self, value):
        self.bpm = value

    def init_midi(self):
        input_ports = mido.get_input_names()
    
        if not input_ports:
            print("No MIDI input ports found.")
            sys.exit(1)
        
        self.inport = mido.open_input()
        self.outport = mido.open_output()

    def play_pre_count(self):
        beat_interval = 60 / self.bpm
        for _ in range(4):  # 4 beat count-in
            QSound.play("/usr/share/sounds/freedesktop/stereo/complete.oga")  # adjust path for your system
            time.sleep(beat_interval)

    def record(self):
        self.stop()
        self.status.setText("Status: Pre-counting...")
        threading.Thread(target=self._record_thread).start()

    def _record_thread(self):
        self.play_pre_count()
        self.status.setText("Status: Recording...")
        self.recording = True
        self.start_time = time.time()
        self.recorded_messages = []

        while self.recording:
            for msg in self.inport.iter_pending():
                if not msg.is_meta:
                    msg.time = time.time() - self.start_time
                    self.recorded_messages.append(msg)

    def play(self):
        self.stop()
        self.status.setText("Status: Playing...")
        self.playing = True
        threading.Thread(target=self._play_thread).start()

    def _play_thread(self):
        if not self.recorded_messages:
            self.status.setText("Status: Nothing to play")
            return

        start_time = time.time()
        for msg in self.recorded_messages:
            if not self.playing:
                break
            time.sleep(max(0, msg.time - (time.time() - start_time)))
            self.outport.send(msg)

        self.status.setText("Status: Idle")
        self.playing = False

    def overdub(self):
        if not self.recorded_messages:
            self.status.setText("Status: Record something first")
            return
        self.stop()
        self.status.setText("Status: Overdubbing...")
        threading.Thread(target=self._overdub_thread).start()

    def _overdub_thread(self):
        self.playing = True
        self.recording = True
        self.start_time = time.time()
        base_messages = list(self.recorded_messages)
        overdub_messages = []

        threading.Thread(target=self._play_thread).start()

        while self.recording:
            for msg in self.inport.iter_pending():
                if not msg.is_meta:
                    msg.time = time.time() - self.start_time
                    overdub_messages.append(msg)

        self.recorded_messages = base_messages + overdub_messages
        self.status.setText("Status: Overdub complete")

    def stop(self):
        self.recording = False
        self.playing = False
        self.status.setText("Status: Stopped")

    def save(self):
        if not self.recorded_messages:
            self.status.setText("Status: Nothing to save")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Save MIDI", "", "MIDI files (*.mid)")
        if path:
            mid = MidiFile()
            track = MidiTrack()
            mid.tracks.append(track)

            prev_time = 0
            for msg in self.recorded_messages:
                delta = int((msg.time - prev_time) * mido.second2tick(1, ticks_per_beat=480, tempo=bpm2tempo(self.bpm)))
                prev_time = msg.time
                msg.time = delta
                track.append(msg)

            mid.save(path)
            self.status.setText(f"Status: Saved to {path}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MidiLooper()
    window.show()
    sys.exit(app.exec_())
