from PyQt5.QtCore import QSettings, QThread, pyqtSignal

import sys
import os
import time
import threading
import mido
from mido import MidiFile, MidiTrack, Message, bpm2tempo
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QLabel,
    QFileDialog, QTreeView, QFileSystemModel, QSpinBox, QStackedWidget, QProgressBar, QFrame, QListWidget, QGridLayout, QLineEdit
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPainter, QColor
# import rtmidih
import simpleaudio as sa  # For playing .wav files


class StatusLED(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.color = QColor("gray")
        self.setFixedSize(30, 30)

    def set_color(self, color_name):
        if self.color.name() != QColor(color_name).name():  # Only update if the color changes
            try:
                self.color = QColor(color_name)
                self.update()
            except Exception as e:
                print(f"Error setting color: {e}")
            

    def paintEvent(self, event):
        print("paintEvent called")
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setBrush(self.color)
            painter.setPen(Qt.NoPen)
            radius = min(self.width(), self.height()) // 2
            painter.drawEllipse(self.rect().center(), radius, radius)
        finally:
            painter.end()  # Ensure the painter is properly ended


class MidiLoaderThread(QThread):
    midi_loaded = pyqtSignal(list)  # Signal to send loaded MIDI messages

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        try:
            mid = mido.MidiFile(self.file_path)
            messages = [msg for msg in mid if not msg.is_meta]
            self.midi_loaded.emit(messages)
        except Exception as e:
            print(f"Error loading MIDI: {e}")
            self.midi_loaded.emit([])  # Emit an empty list on error


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
        self.wav_cache = {}  # Cache for loaded .wav files
        self.button_grid = None
        self.num_buttons = 16  # Default number of buttons
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

        # BPM label and selector in one row
        bpm_layout = QHBoxLayout()
        bpm_label = QLabel("BPM:")
        self.bpm = 120
        self.bpm_spin = QSpinBox()
        self.bpm_spin.setRange(40, 300)
        self.bpm_spin.setValue(self.bpm)  # Default BPM
        bpm_layout.addWidget(bpm_label)
        bpm_layout.addWidget(self.bpm_spin)

        self.track_progress = QProgressBar()

        # Control buttons with ASCII icons
        controls_layout = QHBoxLayout()

        self.play_btn = QPushButton("▶")  # ASCII for Play
        self.play_btn.setToolTip("Play")
        self.play_btn.clicked.connect(self.play)
        # self.play_btn.clicked.connect(self.play_queue)

        self.stop_btn = QPushButton("■")  # ASCII for Stop
        self.stop_btn.setToolTip("Stop")
        self.stop_btn.clicked.connect(self.stop)

        self.record_loop_btn = QPushButton("●")  # ASCII for Record
        self.record_loop_btn.setToolTip("Record & Loop")
        # TODO: rework record or record and loop func
        self.record_loop_btn.clicked.connect(self.record)
        # self.record_loop_btn.clicked.connect(self.record_and_loop)


        self.overdub_btn = QPushButton("⟳")  # ASCII for Overdub
        self.overdub_btn.setToolTip("Overdub")
        self.overdub_btn.clicked.connect(self.overdub)

        # Add buttons to the horizontal layout
        controls_layout.addWidget(self.play_btn)
        controls_layout.addWidget(self.stop_btn)
        controls_layout.addWidget(self.record_loop_btn)
        controls_layout.addWidget(self.overdub_btn)

        # Additional buttons
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self.save)

        self.panic_btn = QPushButton("Panic (All Notes Off)")
        self.panic_btn.clicked.connect(self.panic)

        self.looper_channel_spin = QSpinBox()
        self.looper_channel_spin.setRange(0, 15)
        self.looper_channel_spin.setPrefix("Looper Ch: ")

        self.looper_led = QLabel("●")
        self.set_led(self.looper_led, "gray")


        # Sample button grid
        self.grid_layout = QGridLayout()
        self.update_button_grid()

        # Input field to adjust the number of buttons
        self.num_buttons_input = QLineEdit()
        self.num_buttons_input.setPlaceholderText("Enter number of buttons")
        self.num_buttons_input.returnPressed.connect(self.adjust_button_grid)

        # Add widgets to the main layout
        layout.addWidget(self.led)
        layout.addLayout(bpm_layout)
        layout.addWidget(self.bpm_spin)
        layout.addWidget(self.track_progress)
        layout.addLayout(controls_layout)  
        # layout.addWidget(self.record_btn)
        layout.addWidget(self.record_loop_btn)
        layout.addWidget(self.save_btn)
        layout.addWidget(self.panic_btn)
        layout.addWidget(self.looper_channel_spin)
        layout.addWidget(self.looper_led)
        layout.addWidget(self.status)# Add the controls row
        layout.addLayout(self.grid_layout)
        layout.addWidget(self.num_buttons_input)

        self.looper_view.setLayout(layout)

    def update_button_grid(self):
        """Update the grid of buttons based on the number of buttons."""
        if self.button_grid:
            # Clear existing buttons
            for i in reversed(range(self.grid_layout.count())):
                widget = self.grid_layout.itemAt(i).widget()
                if widget:
                    widget.deleteLater()

        self.button_grid = []
        for i in range(self.num_buttons):
            # Calculate the note name for the button
            note_number = 60 + i  # Start from MIDI note 60 (C4)
            note_name = midi_note_to_name(note_number)

            # Create a button with the note name
            button = QPushButton(note_name)
            button.clicked.connect(lambda _, b=i: self.assign_sample_to_button(b))
            self.grid_layout.addWidget(button, i // 4, i % 4)  # Arrange in a 4-column grid
            self.button_grid.append(button)

    def adjust_button_grid(self):
        """Adjust the number of buttons in the grid."""
        try:
            self.num_buttons = int(self.num_buttons_input.text())
            self.update_button_grid()
        except ValueError:
            self.set_status("Invalid number of buttons", "red")

    def assign_wav_to_button(self, button_index, wav_path):
        """Assign a .wav file to a button."""
        try:
            wave_obj = sa.WWaveObject.from_wave_file(wav_path)
            self.wav_cache[button_index] = wave_obj
            self.set_status(f"Assigned {wav_path} to Button {button_index + 1}", "green")
        except Exception as e:
            self.set_status(f"Failed to load .wav: {e}", "red")

    def assign_sample_to_button(self, button_index):
        """Open a file dialog to assign a .wav file to a button."""
        wav_path, _ = QFileDialog.getOpenFileName(self, "Select WAV File", "", "WAV files (*.wav)")
        if wav_path:
            self.assign_wav_to_button(button_index, wav_path)
            # Update the button text to indicate a sample is assigned
            note_number = 60 + button_index  # Start from MIDI note 60 (C4)
            note_name = midi_note_to_name(note_number)
            self.button_grid[button_index].setText(f"{note_name} (Sample Assigned)")

    def play_assigned_wav(self, button_index):
        """Play the .wav file assigned to a button."""
        if button_index in self.wav_cache:
            self.wav_cache[button_index].play()
        else:
            self.set_status(f"No .wav assigned to Button {button_index + 1}", "red")

    def setup_file_browser_view(self):
        layout = QHBoxLayout()  # Change to QHBoxLayout to place widgets side by side

        # Left side: File browser
        file_browser_layout = QVBoxLayout()

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

        file_browser_layout.addWidget(self.add_folder_btn)
        file_browser_layout.addWidget(self.tree)
        file_browser_layout.addWidget(self.player_channel_spin)
        file_browser_layout.addWidget(self.player_progress)
        file_browser_layout.addWidget(self.player_stop_btn)
        file_browser_layout.addWidget(self.player_led)

        # Right side: Note list
        self.note_list = QListWidget()

        # Add both layouts to the main layout
        layout.addLayout(file_browser_layout)
        layout.addWidget(self.note_list)

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

    def play_pre_count(self):
        beat_interval = 60 / self.bpm
        for _ in range(4):  # 4 beat count-in
            # QSound.play("/usr/share/sounds/freedesktop/stereo/complete.oga")  # adjust path for your system
            # update status led with the count
            self.set_status(f"{_+1}", "gray")
            time.sleep(beat_interval)

    def _record_thread(self):
        self.play_pre_count()
        start = time.time()
        self.set_status("Recording...", "red")
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
        # Stop the currently playing MIDI file, if any
        self.stop_midi_file()

        # Set status and clear the note list
        self.set_status("Loading MIDI file...", "gray")
        self.note_list.clear()

        # Create and start the loader thread
        self.loader_thread = MidiLoaderThread(file_path)
        self.loader_thread.midi_loaded.connect(self.on_midi_loaded)
        self.loader_thread.start()

    def on_midi_loaded(self, messages):
        self.midi_player_messages = messages
        if not messages:
            self.set_status("Failed to load MIDI file", "red")
            return

        self.playing_midi_file = True
        self.set_led(self.player_led, "green")
        self.set_status("MIDI file loaded", "green")

        # Populate the note list
        self.note_list.clear()
        for msg in self.midi_player_messages:
            if msg.type == 'note_on':
                self.note_list.addItem(f"Note: {msg.note}, Velocity: {msg.velocity}, Time: {msg.time}")

        # Start playback in a separate thread
        threading.Thread(target=self._loop_play_midi_file).start()

    def _loop_play_midi_file(self):
        """Play the loaded MIDI file and update the progress bar."""
        if not self.midi_player_messages:
            return

        # Calculate the total duration of the MIDI file in seconds
        ticks_per_beat = self.midi_player_messages[0].ticks_per_beat if hasattr(self.midi_player_messages[0], 'ticks_per_beat') else 480
        tempo = bpm2tempo(self.bpm_spin.value())  # Convert BPM to microseconds per beat
        total_ticks = sum(msg.time for msg in self.midi_player_messages)
        total_duration = mido.tick2second(total_ticks, ticks_per_beat, tempo)

        start_time = time.time()
        elapsed_time = 0

        for msg in self.midi_player_messages:
            if not self.playing_midi_file:
                break

            # Calculate the time to wait for the next message
            wait_time = mido.tick2second(msg.time, ticks_per_beat, tempo)
            time.sleep(wait_time)

            # Send the MIDI message
            msg.channel = self.player_channel_spin.value()
            self.outport.send(msg)

            # Update the progress bar
            elapsed_time = time.time() - start_time
            progress = int((elapsed_time / total_duration) * 100)
            self.player_progress.setValue(progress)

        # Reset the progress bar when playback is complete
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
    def play_queue(self):
        if self.midi_queue.count() == 0:
            self.set_status("No MIDI files in the queue", "red")
            return

        self.current_queue_index = 0
        self.play_next_in_queue()

    def play_next_in_queue(self):
        if self.current_queue_index >= self.midi_queue.count():
            self.current_queue_index = 0  # Loop back to the first file

        file_path = self.midi_queue.item(self.current_queue_index).text()
        self.current_queue_index += 1

        self.load_and_play_midi(file_path)

        # Start a thread to monitor when the current file finishes
        threading.Thread(target=self._monitor_playback).start()

    def _monitor_playback(self):
        while self.playing_midi_file:
            time.sleep(0.1)  # Check every 100ms

        # When the current file finishes, play the next one
        self.play_next_in_queue()

def midi_note_to_name(note_number):
    """Convert MIDI note number to note name."""
    note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    octave = (note_number // 12) - 1
    note = note_names[note_number % 12]
    return f"{note}{octave}"

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MidiLooperPlayerApp()
    window.show()
    sys.exit(app.exec_())
