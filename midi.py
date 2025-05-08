import mido
from mido import Message, MidiFile, MidiTrack, bpm2tempo
import time


print("available midi output ports")
print(mido.get_output_names())


# Configuration
bpm = 60
note = 61  # C#4
velocity = 100
channel = 0  # MIDI channel 1 (0-based)
bars = 4
beats_per_bar = 4
note_length_beats = 1  # 1 beat long
output_port_name = None  # Change if needed

# Calculate timing
tempo = bpm2tempo(bpm)  # microseconds per beat
beat_duration = 60.0 / bpm
loop_duration = bars * beats_per_bar * beat_duration

# Open output port
output = mido.open_output(output_port_name or mido.get_output_names()[0])
print(f"Using MIDI output: {output.name}")

# Create and send note loop
print(f"Sending loop at {bpm} BPM with note C#4 on MIDI channel 1...")

while True:
    for bar in range(bars):
        for beat in range(beats_per_bar):
            # Note on
            output.send(Message('note_on', note=note, velocity=velocity, channel=channel))
            time.sleep(beat_duration * note_length_beats)
            # Note off
            output.send(Message('note_off', note=note, velocity=0, channel=channel))
            # Wait for the rest of the beat if note is shorter
            time.sleep(beat_duration * (1 - note_length_beats))
