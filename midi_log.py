import mido
import threading

def log_messages(port_name):
    try:
        with mido.open_input(port_name) as inport:
            print(f"[{port_name}] Listening...")
            for msg in inport:
                print(f"[{port_name}] {msg}")
    except Exception as e:
        print(f"Error on {port_name}: {e}")

def main():
    input_ports = mido.get_input_names()
    
    if not input_ports:
        print("No MIDI input ports found.")
        return

    print("Starting to log from all MIDI input ports:")
    for i, name in enumerate(input_ports):
        print(f"{i}: {name}")

    # Start a thread for each input port
    threads = []
    for port in input_ports:
        thread = threading.Thread(target=log_messages, args=(port,), daemon=True)
        thread.start()
        threads.append(thread)

    print("\nPress Ctrl+C to stop.")
    try:
        # Keep the main thread alive
        while True:
            pass
    except KeyboardInterrupt:
        print("\nStopping MIDI logger...")

if __name__ == "__main__":
    main()
