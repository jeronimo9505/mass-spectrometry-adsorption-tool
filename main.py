import os
import sys
import argparse

# Ensure current directory is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from gui.main_window import MainWindow

def main():
    parser = argparse.ArgumentParser(description="Lab Vault — Sample Logbook & CO2 Mass Spectrometry Tool")
    parser.add_argument("file", nargs="?", default=None, help="Path to .asc file to open directly")
    parser.add_argument("--sample", default=None, help="Sample ID to preselect")
    args = parser.parse_args()

    app = MainWindow()

    # Preselect sample if requested
    if args.sample and args.sample in app.vault.logbook:
        app.on_sample_selected_in_logbook(args.sample, switch_tab=True)

    # Open specific file if requested
    if args.file and os.path.exists(args.file):
        app.on_open_mass_spec(args.sample, os.path.abspath(args.file))

    app.mainloop()

if __name__ == "__main__":
    main()
