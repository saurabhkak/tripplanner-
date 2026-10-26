"""Main entry point for Multi-Modal Trip Planner."""

from booking import confirm_booking, display_options, select_mode
from storage import save_booking, view_all_bookings
from transport import GEOAPIFY_API_KEY_ENV, geoapify_enabled, get_options


def show_flowchart():
    """Show project flow before the menu starts."""
    print("\nProject Flowchart")
    print("=================")
    print("Start")
    print("  |")
    print("  v")
    print("Main Menu")
    print("  |-- Plan a Trip")
    print("  |     |-- Enter source and destination")
    print("  |     |-- transport.py finds Geoapify/static options")
    print("  |     |-- booking.py displays and confirms choice")
    print("  |     '-- storage.py saves booking in bookings.json")
    print("  |")
    print("  |-- View My Bookings")
    print("  |     '-- storage.py loads bookings.json")
    print("  |")
    print("  '-- Exit")


def main():
    print("\nWelcome to Multi-Modal Trip Planner!")
    print("====================================")
    show_flowchart()

    if geoapify_enabled():
        print("\nGeoapify API: ON")
    else:
        print(f"\nGeoapify API: OFF")
        print(f"Add {GEOAPIFY_API_KEY_ENV} in .env to use live route data.")

    while True:
        print("\nMenu:")
        print("1. Plan a Trip")
        print("2. View My Bookings")
        print("3. Exit")

        choice = input("\nEnter choice (1/2/3): ").strip()

        if choice == "1":
            source = input("\nEnter source city      : ").strip()
            destination = input("Enter destination city : ").strip()

            if not source or not destination:
                print("\nSource and destination are required.")
                continue

            options = get_options(source, destination)

            if options is None:
                print(f"\nSorry! No routes found for {source} -> {destination}")
                if geoapify_enabled():
                    print("Geoapify key found, but live route lookup failed.")
                    print("Check that your Geoapify key is active and has routing/geocoding access.")
                else:
                    print("Add GEOAPIFY_API_KEY in .env for live routes.")
                print("Static demo routes: Mumbai-Pune, Mumbai-Delhi, Pune-Goa")
                continue

            display_options(source, destination, options)
            mode = select_mode(options)
            selected = options[mode]

            if confirm_booking(source, destination, mode, selected):
                save_booking(source, destination, mode, selected)
            else:
                print("\nBooking cancelled.")

        elif choice == "2":
            view_all_bookings()

        elif choice == "3":
            print("\nThank you for using Trip Planner. Bye!")
            break

        else:
            print("Invalid choice. Please enter 1, 2, or 3.")


if __name__ == "__main__":
    import sys

    if "--cli" in sys.argv[1:]:
        main()
    else:
        from gui import main as launch_gui

        launch_gui()
