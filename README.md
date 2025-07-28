# Arcdps Log Uploader

A lightweight, background utility for Windows that automatically watches for new Guild Wars 2 arcdps combat logs and uploads them to [dps.report](https://dps.report). It provides a local web dashboard to view your recent uploads and a system tray icon for easy access.

## Features

- **Automatic Uploads:** Monitors your log folder (and all subfolders) in real-time.
- **System Tray Icon:** Runs quietly in the background with a convenient tray menu for status updates and quick actions.
- **Flexible Upload Modes:** Choose to upload logs instantly, only while playing, or after your gaming session ends.
- **Desktop Notifications:** Get optional pop-up notifications for each successful upload.
- **Autostart with Windows:** Conveniently set the application to start automatically when you log in.
- **Persistent Tracking:** Never uploads the same log twice, even after restarting the app.
- **Packaged Executable:** Easy to use, with a custom icon bundled directly into the single `.exe` file.

## Installation & Usage

1. Go to the [**Releases**](https://github.com/puffyracoon/Arcdps-Log-Uploader/releases) page on GitHub.
2. Download the latest `arcdps_uploader.exe` file from the "Assets" section.
3. Place the `.exe` anywhere you like and double-click it to run.
4. The first time you run it, a window will pop up asking you to select your `arcdps.cbtlogs` folder.
5. The application will now run in the background. You can find its icon in your system tray to check its status or access the menu.

## Configuration

You can customize the application's behavior by right-clicking the tray icon and selecting "Open Config File".

-   **EnableAutostart:** Set to `true` to have the program start automatically with Windows.
-   **EnableNotifications:** Set to `true` to receive a Windows notification for each successful upload.
-   **OnlyUploadWhileGameRunning:** Set to `true` to only upload logs when `Gw2-64.exe` is running.
-   **OnlyUploadAfterGameCloses:** Set to `true` to wait until you close `Gw2-64.exe` and then upload all logs from that session.

*Note: If both `OnlyUpload...` options are set to `false`, the application will upload logs immediately as they are created.*

## Application Statuses

- **PENDING:** The application is starting up, shutting down, or waking up.
- **UPLOADING:** Actively processing and uploading logs.
- **UP TO DATE:** The application is running and waiting for new logs.
- **SLEEPING:** The application is paused because of your selected upload settings (e.g., waiting for the game to start or close).
- **DISCONNECTED:** Cannot connect to dps.report or the local web server failed to start.

## Troubleshooting

If the application is not working correctly or crashes, please check the **`app_log.txt`** file. This file is created in the same folder as the `.exe` and contains detailed status messages and error reports that can help identify the problem.

## How to Build from Source

1. Clone the repository: `git clone https://github.com/puffyracoon/Arcdps-Log-Uploader.git`
2. Navigate into the project directory: `cd Arcdps-Log-Uploader`
3. Create a virtual environment: `python -m venv .venv`
4. Activate it: `.venv\Scripts\activate`
5. Install the dependencies: `pip install -r requirements.txt`
6. To run the script directly: `python arcdps_uploader_pro.py`
7. To build the `.exe`: `pyinstaller --windowed --onefile --name arcdps_uploader --add-data "arc-dps-uploader.ico;." arcdps_uploader_pro.py`

*The final executable will be in the `dist` folder.*

## License

This project is open source and available under the [MIT License](LICENSE).