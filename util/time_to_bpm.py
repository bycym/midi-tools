from mido import MidiFile, bpm2tempo, tempo2bpm

def get_overall_bpm(file_path):
    mid = MidiFile(file_path)
    tempos = []
    ticks_per_beat = mid.ticks_per_beat

    # Iterate through all tracks and collect tempo changes
    for track in mid.tracks:
        current_time = 0
        for msg in track:
            current_time += msg.time
            if msg.type == 'set_tempo':
                tempo = msg.tempo  # Tempo in microseconds per quarter note
                bpm = tempo2bpm(tempo)  # Convert to BPM
                tempos.append((current_time, bpm))

    if not tempos:
        # Default MIDI tempo is 120 BPM if no tempo changes are found
        return 120

    # Calculate the weighted average BPM
    total_time = 0
    weighted_bpm_sum = 0
    for i in range(len(tempos)):
        start_time = tempos[i][0]
        bpm = tempos[i][1]
        if i < len(tempos) - 1:
            end_time = tempos[i + 1][0]
        else:
            end_time = mid.length * ticks_per_beat  # Use the total length of the MIDI file

        duration = end_time - start_time
        total_time += duration
        weighted_bpm_sum += bpm * duration

    overall_bpm = weighted_bpm_sum / total_time
    return overall_bpm
