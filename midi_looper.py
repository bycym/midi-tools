from PyQt5.QtCore import QSettings

import sys
import os
import time
import threading
import mido
from mido import MidiFile, MidiTrack, Message, bpm2tempo
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QLabel,
    QFileDialog, QTreeView, QFileSystemModel, QSpinBox, QStackedWidget, QProgressBar, QFrame
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPainter, QColor
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


class MidiLooperPlayerApp(QWidget):
    def __init__(self):
        super().__init__()

        self.setAcceptDrops(True)
        self.led = StatusLED()
        self.status = QLabel("Status: Idle")

        self.setWindowTitle("MIDI Looper and Player")
        self.resize(800, 600)
        self.setAcceptDrops(True)

        self.outport = mido.open_output()  # Use IAC for macOS global output
        self.recorded_messages = []
        self.is_recording = False
        self.is_playing = False
        self.is_overdubbing = False
        self.playing_midi_file = False
        self.midi_player_messages = []
        self.midi_player_channel = 0
        self.looper_channel = 0
        self.settings = QSettings("MyCompany", "MidiLooperApp")
        self.init_ui()
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_progress)

    def init_ui(self):
        self.stack = QStackedWidget()
        self.looper_view = QWidget()
        self.file_browser_view = QWidget()

        self.setup_looper_view()
        self.setup_file_browser_view()

        self.stack.addWidget(self.looper_view)
        self.stack.addWidget(self.file_browser_view)

        self.toggle_btn = QPushButton("Switch to File Browser")
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.clicked.connect(self.toggle_view)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.toggle_btn)
        main_layout.addWidget(self.stack)

    def setup_looper_view(self):
        layout = QVBoxLayout()

        bpm_label = QLabel("BPM:")
        self.bpm = 120
        self.bpm_spin = QSpinBox()
        self.bpm_spin.setRange(40, 300)
        self.bpm_spin.setValue(self.bpm)

        self.track_progress = QProgressBar()

        self.record_btn = QPushButton("Record")
        self.record_btn.clicked.connect(self.record)

        self.record_loop_btn = QPushButton("Record & Loop")
        self.record_loop_btn.clicked.connect(self.record_and_loop)

        self.play_btn = QPushButton("Play")
        self.play_btn.clicked.connect(self.play)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self.stop)

        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self.save)

        self.overdub_btn = QPushButton("Overdub")
        self.overdub_btn.clicked.connect(self.overdub)

        self.panic_btn = QPushButton("Panic (All Notes Off)")
        self.panic_btn.clicked.connect(self.panic)

        self.looper_channel_spin = QSpinBox()
        self.looper_channel_spin.setRange(0, 15)
        self.looper_channel_spin.setPrefix("Looper Ch: ")

        self.looper_led = QLabel("●")
        self.set_led(self.looper_led, "gray")

        layout.addWidget(bpm_label)
        layout.addWidget(self.bpm_spin)
        layout.addWidget(self.track_progress)
        layout.addWidget(self.record_btn)
        layout.addWidget(self.record_loop_btn)
        layout.addWidget(self.play_btn)
        layout.addWidget(self.stop_btn)
        layout.addWidget(self.save_btn)
        layout.addWidget(self.overdub_btn)
        layout.addWidget(self.panic_btn)
        layout.addWidget(self.looper_channel_spin)
        layout.addWidget(self.looper_led)
        layout.addWidget(self.status)

        self.looper_view.setLayout(layout)

    def setup_file_browser_view(self):
        layout = QVBoxLayout()

        self.add_folder_btn = QPushButton("Add Folder")
        self.add_folder_btn.clicked.connect(self.add_folder)

        self.tree = QTreeView()
        self.model = QFileSystemModel()
        self.model.setNameFilters(["*.mid", "*.midi"])
        self.model.setNameFilterDisables(False)
        self.tree.setModel(self.model)
        self.tree.clicked.connect(self.play_selected_midi)

        self.player_channel_spin = QSpinBox()
        self.player_channel_spin.setRange(0, 15)
        self.player_channel_spin.setPrefix("Player Ch: ")

        self.player_stop_btn = QPushButton("Stop MIDI File")
        self.player_stop_btn.clicked.connect(self.stop_midi_file)

        self.player_progress = QProgressBar()

        self.player_led = QLabel("●")
        self.set_led(self.player_led, "gray")

        layout.addWidget(self.add_folder_btn)
        layout.addWidget(self.tree)
        layout.addWidget(self.player_channel_spin)
        layout.addWidget(self.player_progress)
        layout.addWidget(self.player_stop_btn)
        layout.addWidget(self.player_led)

        self.file_browser_view.setLayout(layout)

        last_folder = self.settings.value("lastMidiFolder")
        if last_folder and os.path.isdir(last_folder):
            self.model.setRootPath(last_folder)
            self.tree.setRootIndex(self.model.index(last_folder))

    def set_status(self, text, color=None):
        self.status.setText(f"Status: {text}")
        if color:
            self.led.set_color(color)

    def update_progress(self):
        if self.recording or self.playing or self.overdubbing:
            elapsed = time.time() - self.start_time
            progress_value = int((elapsed % 10) * 100)  # wrap every 10s
            self.track_bar.setValue(progress_value)

    def toggle_view(self):
        if self.toggle_btn.isChecked():
            self.toggle_btn.setText("Switch to Looper")
            self.stack.setCurrentWidget(self.file_browser_view)
        else:
            self.toggle_btn.setText("Switch to File Browser")
            self.stack.setCurrentWidget(self.looper_view)

    def record(self):
        self.recorded_messages.clear()
        self.is_recording = True
        self.set_led(self.looper_led, "red")
        self.set_status("Pre-counting...", "gray")
        threading.Thread(target=self._record_thread).start()

    def record_and_loop(self):
        self.record()
        threading.Thread(target=self._auto_stop_and_play).start()

    def _auto_stop_and_play(self):
        time.sleep(4 * 60 / self.bpm_spin.value())  # one bar pre-count
        self.is_recording = False
        self.set_led(self.looper_led, "green")
        self.set_status("Pre-counting...", "gray")
        self.play()

    def _record_thread(self):
        start = time.time()
        with mido.open_input() as inport:
            while self.is_recording:
                for msg in inport.iter_pending():
                    msg.time = time.time() - start
                    self.recorded_messages.append(msg)

    def play(self):
        if not self.recorded_messages:
            self.set_status("Nothing to play", "gray")
            return
        self.is_playing = True
        self.set_led(self.looper_led, "green")
        self.set_status("Looping playback...", "green")
        self.loop_start_time = time.time()
        self.timer.start(100)
        threading.Thread(target=self._loop_play).start()

    def _loop_play(self):
        while self.is_playing:
            start = time.time()
            for msg in self.recorded_messages:
                if not self.is_playing:
                    return
                time.sleep(max(0, msg.time - (time.time() - start)))
                msg.channel = self.looper_channel_spin.value()
                self.outport.send(msg)

    def update_progress(self):
        if not self.is_playing or not self.recorded_messages:
            self.track_progress.setValue(0)
            return
        duration = self.recorded_messages[-1].time
        elapsed = (time.time() - self.loop_start_time) % duration
        percent = int((elapsed / duration) * 100)
        self.track_progress.setValue(percent)

    def stop(self):
        self.is_recording = False
        self.is_playing = False
        self.is_overdubbing = False
        self.timer.stop()
        self.track_progress.setValue(0)
        self.set_led(self.looper_led, "gray")
        self.set_status("Stop", "gray")
        self.set_led(self.player_led, "gray")

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

    def overdub(self):
        self.is_overdubbing = True
        self.set_led(self.looper_led, "yellow")

    def panic(self):
        for ch in range(16):
            self.outport.send(Message('control_change', control=123, value=0, channel=ch))

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select MIDI Folder")
        if folder:
            self.settings.setValue("lastMidiFolder", folder)  # Save path
            self.model.setRootPath(folder)
            self.tree.setRootIndex(self.model.index(folder))


    def play_selected_midi(self, index):
        file_path = self.model.filePath(index)
        if os.path.isfile(file_path):
            self.load_and_play_midi(file_path)

    def load_and_play_midi(self, file_path):
        mid = MidiFile(file_path)
        self.midi_player_messages = [msg for msg in mid if not msg.is_meta]
        self.playing_midi_file = True
        self.set_led(self.player_led, "green")
        threading.Thread(target=self._loop_play_midi_file).start()

    def _loop_play_midi_file(self):
        while self.playing_midi_file:
            start = time.time()
            for msg in self.midi_player_messages:
                if not self.playing_midi_file:
                    return
                time.sleep(max(0, msg.time - (time.time() - start)))
                msg.channel = self.player_channel_spin.value()
                self.outport.send(msg)
            self.player_progress.setValue(100)
            time.sleep(0.1)
            self.player_progress.setValue(0)

    def stop_midi_file(self):
        self.playing_midi_file = False
        self.player_progress.setValue(0)
        self.set_led(self.player_led, "gray")

    def set_led(self, label, color):
        label.setStyleSheet(f"color: {color}; font-size: 24px")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.lower().endswith(('.mid', '.midi')):
                self.load_and_play_midi(file_path)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.lower().endswith(('.mid', '.midi')):
                self.load_and_play_midi(file_path)

    def load_and_play_midi(self, file_path):
        try:
            mid = mido.MidiFile(file_path)
            self.midi_player_messages = [msg for msg in mid if not msg.is_meta]
            self.playing_midi_file = True
            self.set_led(self.player_led, "green")
            threading.Thread(target=self._loop_play_midi_file).start()
        except Exception as e:
            print(f"Error loading MIDI: {e}")

    

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MidiLooperPlayerApp()
    window.show()
    sys.exit(app.exec_())
