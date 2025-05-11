import sys, time, os, threading
import mido
from mido import MidiFile, Message
from PyQt5.QtCore import Qt, QTimer, QDir
from PyQt5.QtGui import QColor, QPixmap, QPainter, QPen, QBrush
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, QGraphicsScene,
    QGraphicsView, QGraphicsTextItem, QSpinBox, QHBoxLayout, QCheckBox,
    QFileDialog, QTreeView, QFileSystemModel, QStackedWidget, QGraphicsRectItem
)

class MidiLooperPlayerApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MIDI Looper & Player")

        self.recording = False
        self.playing = False
        self.overdubbing = False
        self.playing_midi_file = False
        self.bpm = 120
        self.recorded_messages = []
        self.midi_player_messages = []

        self.outport = mido.open_output()  # Global MIDI on macOS

        self.init_ui()
        self.init_timer()

    def init_ui(self):
        main_layout = QVBoxLayout()

        self.toggle_view_btn = QPushButton("Switch to File Browser")
        self.toggle_view_btn.setCheckable(True)
        self.toggle_view_btn.clicked.connect(self.toggle_view)
        main_layout.addWidget(self.toggle_view_btn)

        self.stack = QStackedWidget()
        self.init_looper_view()
        self.init_file_browser_view()
        self.stack.addWidget(self.looper_view)
        self.stack.addWidget(self.file_browser_view)
        main_layout.addWidget(self.stack)

        self.setLayout(main_layout)

    def init_looper_view(self):
        self.looper_view = QWidget()
        layout = QVBoxLayout()

        self.record_btn = QPushButton("Record")
        self.play_btn = QPushButton("Play")
        self.overdub_btn = QPushButton("Overdub")
        self.stop_btn = QPushButton("Stop")

        self.record_btn.clicked.connect(self.toggle_recording)
        self.play_btn.clicked.connect(self.toggle_playback)
        self.overdub_btn.clicked.connect(self.toggle_overdub)
        self.stop_btn.clicked.connect(self.stop)

        layout.addWidget(self.record_btn)
        layout.addWidget(self.play_btn)
        layout.addWidget(self.overdub_btn)
        layout.addWidget(self.stop_btn)

        self.looper_led = QLabel("Looper")
        self.player_led = QLabel("Player")
        self.set_led(self.looper_led, "gray")
        self.set_led(self.player_led, "gray")

        looper_controls = QHBoxLayout()
        looper_controls.addWidget(self.looper_led)
        self.looper_mute = QCheckBox("Mute Looper")
        looper_controls.addWidget(self.looper_mute)

        player_controls = QHBoxLayout()
        player_controls.addWidget(self.player_led)
        self.player_mute = QCheckBox("Mute Player")
        player_controls.addWidget(self.player_mute)

        layout.addLayout(looper_controls)
        layout.addLayout(player_controls)

        self.looper_channel_spin = QSpinBox()
        self.looper_channel_spin.setRange(0, 15)
        self.looper_channel_spin.setPrefix("Looper Ch: ")
        layout.addWidget(self.looper_channel_spin)

        self.piano_roll_scene = QGraphicsScene()
        self.piano_roll_view = QGraphicsView(self.piano_roll_scene)
        layout.addWidget(self.piano_roll_view)

        self.waveform_scene = QGraphicsScene()
        self.waveform_view = QGraphicsView(self.waveform_scene)
        layout.addWidget(self.waveform_view)

        self.looper_view.setLayout(layout)

    def init_file_browser_view(self):
        self.file_browser_view = QWidget()
        layout = QVBoxLayout()

        self.add_folder_btn = QPushButton("Add Folder")
        self.add_folder_btn.clicked.connect(self.add_folder)
        layout.addWidget(self.add_folder_btn)

        self.model = QFileSystemModel()
        self.model.setNameFilters(["*.mid", "*.midi"])
        self.model.setNameFilterDisables(False)

        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.clicked.connect(self.play_selected_midi)
        layout.addWidget(self.tree)

        self.player_channel_spin = QSpinBox()
        self.player_channel_spin.setRange(0, 15)
        self.player_channel_spin.setPrefix("Player Ch: ")
        layout.addWidget(self.player_channel_spin)

        self.file_browser_view.setLayout(layout)

    def toggle_view(self):
        if self.toggle_view_btn.isChecked():
            self.toggle_view_btn.setText("Switch to Looper")
            self.stack.setCurrentWidget(self.file_browser_view)
        else:
            self.toggle_view_btn.setText("Switch to File Browser")
            self.stack.setCurrentWidget(self.looper_view)

    def set_led(self, label, color):
        size = 14
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setBrush(QColor(color))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(0, 0, size, size)
        painter.end()
        label.setPixmap(pixmap)

    def toggle_recording(self):
        self.recording = not self.recording
        self.recorded_messages = []
        self.set_led(self.looper_led, "red" if self.recording else "gray")

    def toggle_playback(self):
        if self.playing:
            self.playing = False
            self.set_led(self.looper_led, "gray")
        else:
            self.playing = True
            self.set_led(self.looper_led, "green")
            threading.Thread(target=self.play_loop).start()

    def toggle_overdub(self):
        self.overdubbing = not self.overdubbing
        self.set_led(self.looper_led, "yellow" if self.overdubbing else "green")

    def stop(self):
        self.playing = False
        self.recording = False
        self.overdubbing = False
        self.playing_midi_file = False
        self.set_led(self.looper_led, "gray")
        self.set_led(self.player_led, "gray")

    def play_loop(self):
        while self.playing:
            start = time.time()
            for msg in self.recorded_messages:
                if not self.playing:
                    return
                time.sleep(max(0, msg.time - (time.time() - start)))
                if not self.looper_mute.isChecked():
                    msg.channel = self.looper_channel_spin.value()
                    self.outport.send(msg)

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select MIDI Folder")
        if folder:
            self.model.setRootPath(folder)
            self.tree.setRootIndex(self.model.index(folder))

    def play_selected_midi(self, index):
        file_path = self.model.filePath(index)
        if os.path.isfile(file_path):
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
                if not self.player_mute.isChecked():
                    msg.channel = self.player_channel_spin.value()
                    self.outport.send(msg)

    def init_timer(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_visuals)
        self.timer.start(100)

    def update_visuals(self):
        self.draw_piano_roll()
        self.draw_waveform()

    def draw_piano_roll(self):
        self.piano_roll_scene.clear()
        for i in range(60, 72):
            color = Qt.white if i % 12 not in [1, 3, 6, 8, 10] else Qt.black
            self.piano_roll_scene.addRect((i - 60) * 20, 0, 20, 60, QPen(Qt.black), QBrush(color))
        for i, msg in enumerate(self.recorded_messages):
            if msg.type == "note_on":
                x = i * 20
                y = 60 - (msg.note - 60) * 2
                self.piano_roll_scene.addRect(x, y, 10, 10, QPen(Qt.black), QBrush(Qt.blue))

    def draw_waveform(self):
        self.waveform_scene.clear()
        x = 0
        for msg in self.recorded_messages:
            if msg.type == "note_on":
                self.waveform_scene.addRect(x, 50, 5, 30, QPen(Qt.black), QBrush(Qt.green))
                x += 10

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MidiLooperPlayerApp()
    window.resize(800, 600)
    window.show()
    sys.exit(app.exec_())
