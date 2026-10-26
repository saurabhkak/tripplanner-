"""Booking display, selection, and confirmation logic."""


def display_options(source, destination, options):
    """Print all transport options in a readable table."""
    print(f"\n{'=' * 72}")
    print(f"  Routes: {source.title()} -> {destination.title()}")
    print(f"{'=' * 72}")
    print(f"{'Mode':<10} {'Time':<18} {'Distance':<15} {'Fare (Rs.)':<12} Source")
    print(f"{'-' * 72}")

    for mode, details in options.items():
        print(
            f"{mode.title():<10} "
            f"{details['time']:<18} "
            f"{details.get('distance', 'N/A'):<15} "
            f"Rs.{details['fare']:<9} "
            f"{details.get('source', 'Static data')}"
        )

    print(f"{'=' * 72}")


def select_mode(options):
    """Ask user to choose a transport mode."""
    modes = list(options.keys())
    print("\nAvailable modes:", ", ".join(modes))

    while True:
        choice = input("Enter mode: ").lower().strip()
        if choice in options:
            return choice
        print("Invalid choice. Please try again.")


def confirm_booking(source, destination, mode, details):
    """Show booking summary and ask for confirmation."""
    print("\n--- Booking Summary ---")
    print(f"From     : {source.title()}")
    print(f"To       : {destination.title()}")
    print(f"Mode     : {mode.title()}")
    print(f"Time     : {details['time']}")
    print(f"Distance : {details.get('distance', 'N/A')}")
    print(f"Fare     : Rs.{details['fare']}")
    print(f"Source   : {details.get('source', 'Static data')}")
    print("-----------------------")

    confirm = input("Confirm booking? (yes/no): ").lower().strip()
    return confirm == "yes"
