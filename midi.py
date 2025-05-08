import sys
import time
import mido
from mido import Message
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QFormLayout, QSpinBox, QDoubleSpinBox
)


class MidiApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MIDI ADSR Note Sender")

        self.output_name = next((p for p in mido.get_output_names() if "IAC" in p), None)
        if not self.output_name:
            raise Exception("No IAC MIDI output found. Enable the IAC Driver in Audio MIDI Setup.")

        # --- GUI layout ---
        layout = QFormLayout()

        self.note = QSpinBox(); self.note.setValue(37)  # C#4
        self.velocity = QSpinBox(); self.velocity.setRange(0, 127); self.velocity.setValue(100)
        self.bpm = QDoubleSpinBox(); self.bpm.setValue(60)
        self.duration = QDoubleSpinBox(); self.duration.setValue(2.0)

        self.attack = QDoubleSpinBox(); self.attack.setValue(0.2)
        self.decay = QDoubleSpinBox(); self.decay.setValue(0.2)
        self.sustain = QSpinBox(); self.sustain.setRange(0, 127); self.sustain.setValue(70)
        self.release = QDoubleSpinBox(); self.release.setValue(0.5)
        self.hold_beats = QDoubleSpinBox(); self.hold_beats.setValue(1.0)
        


        layout.addRow("Note (MIDI)", self.note)
        layout.addRow("Velocity", self.velocity)
        layout.addRow("BPM", self.bpm)
        layout.addRow("Duration (s)", self.duration)
        layout.addRow("Attack (s)", self.attack)
        layout.addRow("Decay (s)", self.decay)
        layout.addRow("Sustain (0-127)", self.sustain)
        layout.addRow("Release (s)", self.release)
        layout.addRow("Hold Beats", self.hold_beats)

        self.play_btn = QPushButton("Play Note")
        self.play_btn.clicked.connect(self.send_note)
        self.stop_btn = QPushButton("Send Note Off")
        self.stop_btn.clicked.connect(self.send_note_off)
        # self.hold_btn = QPushButton("Hold Note (1 Beat)")
        # self.hold_btn.clicked.connect(self.hold_note)


        self.toggle_btn = QPushButton("Hold Note")
        self.toggle_btn.setCheckable(True)  # Make it a toggle button
        self.toggle_btn.clicked.connect(self.toggle_hold_note)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.play_btn)
        # button_layout.addWidget(self.hold_btn)
        button_layout.addWidget(self.stop_btn)
        button_layout.addWidget(self.toggle_btn)



        vlayout = QVBoxLayout()
        vlayout.addLayout(layout)
        vlayout.addLayout(button_layout)

        self.setLayout(vlayout)

        self.last_note = None

    def send_note(self):
        note = self.note.value()
        velocity = self.velocity.value()
        bpm = self.bpm.value()
        duration = self.duration.value()
        attack = self.attack.value()
        decay = self.decay.value()
        sustain = self.sustain.value()
        release = self.release.value()

        self.last_note = note

        with mido.open_output(self.output_name) as outport:
            channel = 0

            attack_steps = 10
            for i in range(attack_steps):
                vel = int((i + 1) / attack_steps * velocity)
                outport.send(Message('note_on', note=note, velocity=vel, channel=channel))
                time.sleep(attack / attack_steps)

            decay_steps = 10
            for i in range(decay_steps):
                vel = int(velocity - (velocity - sustain) * ((i + 1) / decay_steps))
                outport.send(Message('note_on', note=note, velocity=vel, channel=channel))
                time.sleep(decay / decay_steps)

            sustain_time = max(0, duration - attack - decay - release)
            outport.send(Message('note_on', note=note, velocity=sustain, channel=channel))
            time.sleep(sustain_time)

            release_steps = 10
            for i in range(release_steps):
                vel = int(sustain * (1 - (i + 1) / release_steps))
                outport.send(Message('note_on', note=note, velocity=max(0, vel), channel=channel))
                time.sleep(release / release_steps)

            outport.send(Message('note_off', note=note, velocity=0, channel=channel))

    def send_note_off(self):
        if self.last_note is not None:
            with mido.open_output(self.output_name) as outport:
                outport.send(Message('note_off', note=self.last_note, velocity=0, channel=0))

    def hold_note(self):
        note = self.note.value()
        velocity = self.velocity.value()
        self.last_note = note
        self.is_note_held = True  # Mark the note as held

        with mido.open_output(self.output_name) as outport:
            outport.send(Message('note_on', note=note, velocity=velocity, channel=0))

    def stop_hold(self):
        if self.is_note_held:
            note = self.last_note
            with mido.open_output(self.output_name) as outport:
                outport.send(Message('note_off', note=note, velocity=0, channel=0))
            self.is_note_held = False  # Reset the hold state


    def toggle_hold_note(self):
        if self.toggle_btn.isChecked():
            # Send note_on when the button is checked (held state)
            self.hold_note()
            self.toggle_btn.setText("Stop Hold")  # Change button text to "Stop Hold"
        else:
            # Send note_off when the button is unchecked (released state)
            self.stop_hold()
            self.toggle_btn.setText("Hold Note")  # Change button text back to "Hold Note"



if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MidiApp()
    window.show()
    sys.exit(app.exec_())
