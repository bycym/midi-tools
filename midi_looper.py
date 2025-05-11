import sys
import time
import threading
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout,
    QLabel, QSpinBox, QFileDialog, QProgressBar, QFrame
)
from PyQt5.QtMultimedia import QSound
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPainter, QColor
from mido import MidiFile, MidiTrack, Message, bpm2tempo
import mido
import rtmidi


class StatusLED(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.color = QColor("gray")
        self.setFixedSize(30, 30)

    def set_color(self, color_name):
        self.color = QColor(color_name)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(self.color)
        painter.setPen(Qt.NoPen)
        radius = min(self.width(), self.height()) // 2
        painter.drawEllipse(self.rect().center(), radius, radius)


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

        self.led = StatusLED()
        self.bpm_label = QLabel("BPM:")
        self.bpm_spin = QSpinBox()
        self.bpm_spin.setRange(40, 300)
        self.bpm_spin.setValue(120)
        self.bpm_spin.valueChanged.connect(self.update_bpm)

        self.status = QLabel("Status: Idle")

        self.track_bar = QProgressBar()
        self.track_bar.setMinimum(0)
        self.track_bar.setMaximum(1000)
        self.track_bar.setValue(0)
        self.track_bar.setTextVisible(False)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_progress)

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

        self.record_loop_btn = QPushButton("Record & Loop")
        self.record_loop_btn.clicked.connect(lambda: self.record(auto_play=True))

        layout.addWidget(self.led)
        layout.addWidget(self.bpm_label)
        layout.addWidget(self.bpm_spin)
        layout.addWidget(self.status)
        layout.addWidget(self.track_bar)
        layout.addWidget(self.record_btn)
        layout.addWidget(self.play_btn)
        layout.addWidget(self.overdub_btn)
        layout.addWidget(self.stop_btn)
        layout.addWidget(self.save_btn)
        layout.addWidget(self.record_loop_btn)

        self.setLayout(layout)

    def update_bpm(self, value):
        self.bpm = value

    def set_status(self, text, color=None):
        self.status.setText(f"Status: {text}")
        if color:
            self.led.set_color(color)

    def update_progress(self):
        if self.recording or self.playing or self.overdubbing:
            elapsed = time.time() - self.start_time
            progress_value = int((elapsed % 10) * 100)  # wrap every 10s
            self.track_bar.setValue(progress_value)

    def init_midi(self):
        available_outputs = mido.get_output_names()
        print("Available MIDI outputs:", available_outputs)

        # Use IAC Bus if available
        iac_port = next((port for port in available_outputs if "IAC" in port), None)
        if iac_port:
            self.outport = mido.open_output(iac_port)
            self.set_status(f"Using IAC: {iac_port}", "gray")
        else:
            self.outport = mido.open_output()  # fallback
            self.set_status("Default MIDI Output", "gray")

        self.inport = mido.open_input()  # optional: also route in from IAC or hardware


    def play_pre_count(self):
        beat_interval = 60 / self.bpm
        for _ in range(4):
            # Replace this path with a real sound file if available
            # QSound.play("count.wav")
            print("Beep")  # Replace with actual sound
            time.sleep(beat_interval)

    def record(self, auto_play=False):
        self.stop()
        self.set_status("Pre-counting...", "gray")
        threading.Thread(target=self._record_thread, args=(auto_play,)).start()


    def _record_thread(self, auto_play):
        self.play_pre_count()
        self.set_status("Recording...", "red")
        self.recording = True
        self.start_time = time.time()
        self.recorded_messages = []
        self.timer.start(100)

        while self.recording:
            for msg in self.inport.iter_pending():
                if not msg.is_meta:
                    msg.time = time.time() - self.start_time
                    print(msg)
                    self.recorded_messages.append(msg)

        self.timer.stop()
        if auto_play and self.recorded_messages:
            self.set_status("Looping playback...", "green")
            self.playing = True
            threading.Thread(target=self._loop_play_thread).start()
        else:
            self.set_status("Idle", "gray")


    def _loop_play_thread(self):
        self.start_time = time.time()
        self.timer.start(100)
        while self.playing:
            start_time = time.time()
            for msg in self.recorded_messages:
                if not self.playing:
                    self.timer.stop()
                    return
                time.sleep(max(0, msg.time - (time.time() - start_time)))
                self.outport.send(msg)


    def play(self):
        if not self.recorded_messages:
            self.set_status("Nothing to play", "gray")
            return

        self.stop()
        self.set_status("Looping playback...", "green")
        self.playing = True
        threading.Thread(target=self._loop_play_thread).start()


    def _play_thread(self):
        if not self.recorded_messages:
            self.set_status("Nothing to play", "gray")
            return

        self.start_time = time.time()
        self.timer.start(100)
        start_time = time.time()

        for msg in self.recorded_messages:
            print(msg)
            if not self.playing:
                break
            time.sleep(max(0, msg.time - (time.time() - start_time)))
            self.outport.send(msg)

        self.timer.stop()
        self.set_status("Idle", "gray")
        self.playing = False

    def overdub(self):
        if not self.recorded_messages:
            self.set_status("Record something first", "gray")
            return
        self.stop()
        self.set_status("Overdubbing...", "yellow")
        threading.Thread(target=self._overdub_thread).start()

    def _overdub_thread(self):
        self.playing = True
        self.recording = True
        self.overdubbing = True
        self.start_time = time.time()
        self.timer.start(100)

        base_messages = list(self.recorded_messages)
        overdub_messages = []

        threading.Thread(target=self._play_thread).start()

        while self.recording:
            for msg in self.inport.iter_pending():
                if not msg.is_meta:
                    msg.time = time.time() - self.start_time
                    print(msg)
                    overdub_messages.append(msg)

        self.recorded_messages = base_messages + overdub_messages
        self.overdubbing = False
        self.timer.stop()
        self.set_status("Overdub complete", "gray")

    def stop(self):
        self.recording = False
        self.playing = False
        self.overdubbing = False
        self.set_status("Stopped", "gray")
        self.timer.stop()


    def save(self):
        if not self.recorded_messages:
            self.set_status("Nothing to save", "gray")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Save MIDI", "", "MIDI files (*.mid)")
        if path:
            mid = MidiFile()
            track = MidiTrack()
            mid.tracks.append(track)

            prev_time = 0
            for msg in self.recorded_messages:
                delta = int((msg.time - prev_time) * mido.second2tick(
                    1, ticks_per_beat=480, tempo=bpm2tempo(self.bpm)))
                prev_time = msg.time
                msg.time = delta
                track.append(msg)

            mid.save(path)
            self.set_status(f"Saved to {path}", "gray")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MidiLooper()
    window.show()
    sys.exit(app.exec_())
