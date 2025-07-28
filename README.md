# Arcdps Log Uploader

A lightweight, background utility for Windows that automatically watches for new Guild Wars 2 arcdps combat logs and uploads them to [dps.report](https://dps.report). It provides a local web dashboard to view your recent uploads and a system tray icon for easy access.

## Features

- **Automatic Uploads:** Monitors your log folder (and all subfolders) in real-time.
- **System Tray Icon:** Runs quietly in the background with a convenient tray menu for status updates and quick actions.
- **Local Web Dashboard:** View a list of your current session's uploads at `http://localhost:8000`.
- **Persistent Tracking:** Never uploads the same log twice, even after restarting the app.
- **First-Time Setup:** Automatically prompts you to select your log folder on the first run.
- **Packaged Executable:** Easy to use, with a custom icon bundled directly into the single `.exe` file.

## Installation & Usage

1. Go to the [**Releases**](https://github.com/YourUsername/Arcdps-Log-Uploader/releases) page on GitHub.
2. Download the latest `arcdps_uploader.exe` file from the "Assets" section.
3. Place the `.exe` anywhere you like and double-click it to run.
4. The first time you run it, a window will pop up asking you to select your `arcdps.cbtlogs` folder.
5. The application will now run in the background. You can find its icon in your system tray to check its status or access the menu.

## Application Statuses

You can check what the application is doing by hovering over the tray icon or opening the menu.

- **PENDING:** The application is starting up or shutting down.
- **UPLOADING:** Actively processing and uploading logs. If there's a backlog, it will show progress (e.g., "Initial scan... (5/20)").
- **UP TO DATE:** The application is running and has successfully processed all available logs. It is now waiting for new ones.
- **DISCONNECTED:** Cannot connect to dps.report or the local web server failed to start. This could be due to an internet issue or another program using the same port.
- **SLEEPING:** (Feature not yet implemented) The application will pause when Guild Wars 2 is not running.

## How to Build from Source

If you want to modify the code or build the executable yourself:

1. Clone the repository: `git clone https://github.com/YourUsername/Arcdps-Log-Uploader.git`
2. Navigate into the project directory: `cd Arcdps-Log-Uploader`
3. Create a virtual environment: `python -m venv .venv`
4. Activate it: `.venv\Scripts\activate`
5. Install the dependencies: `pip install -r requirements.txt`
6. To run the script directly: `python arcdps_uploader_pro.py`
7. To build the `.exe`: `pyinstaller --windowed --onefile --name arcdps_uploader --add-data "arc-dps-uploader.ico;." arcdps_uploader_pro.py`

*The final executable will be in the `dist` folder.*

## License

This project is open source and available under the [MIT License](LICENSE).