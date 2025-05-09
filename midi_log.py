import mido

def list_input_ports():
    print("Available MIDI input ports:")
    for i, port in enumerate(mido.get_input_names()):
        print(f"{i}: {port}")

def main():
    list_input_ports()
    port_name = input("Enter the name or number of the MIDI input port to use: ")

    try:
        # If the user entered a number, get the corresponding port name
        if port_name.isdigit():
            port_name = mido.get_input_names()[int(port_name)]

        with mido.open_input(port_name) as inport:
            print(f"Listening for MIDI messages on: {port_name}")
            for msg in inport:
                print(msg)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
