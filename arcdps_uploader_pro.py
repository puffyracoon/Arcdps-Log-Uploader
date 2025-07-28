import os
import sys
import time
import requests
import threading
import json
import webbrowser
import configparser
import tkinter as tk
from tkinter import filedialog
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pystray import MenuItem as item, Icon
from PIL import Image, ImageDraw
import logging
import psutil
import winreg
from win10toast_persist import ToastNotifier

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='app_log.txt',
    filemode='w'
)

CONFIG_FILE = "config.ini"
UPLOADED_LOGS_TRACKER_FILE = "uploaded_logs.txt"
APP_NAME = "Arcdps Log Uploader"
ICON_FILE = "arc-dps-uploader.ico"
GAME_PROCESS_NAME = "Gw2-64.exe"

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def update_autostart_registry(app_name, enable):
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        exe_path = sys.executable if hasattr(sys, '_MEIPASS') else f'"{sys.executable}" "{os.path.abspath(__file__)}"'
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS) as key:
            if enable:
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, exe_path)
                logging.info(f"Enabled autostart: Set registry key for {app_name}.")
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                    logging.info(f"Disabled autostart: Removed registry key for {app_name}.")
                except FileNotFoundError:
                    logging.info("Autostart was already disabled.")
    except Exception as e:
        logging.error(f"Failed to update registry for autostart", exc_info=True)

class AppStatus:
    def __init__(self, app_instance, tray_icon):
        self._app = app_instance
        self._status = "PENDING"
        self._details = "Initializing..."
        self._tray_icon = tray_icon

    @property
    def status_text(self):
        return f"Status: {self._status} - {self._details}"

    def set(self, status, details=""):
        self._status = status
        self._details = details
        logging.info(f"Status changed: {self.status_text}")
        self.update()

    def update(self):
        if self._tray_icon.HAS_MENU:
            self._tray_icon.menu = self._app.menu_factory()

class LogUploaderApp:
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.tray_icon = None
        self.status = None
        self.folder_to_watch = ""
        self.web_server_port = 8000
        self.uploaded_logs_for_web = []
        self.web_logs_lock = threading.Lock()
        self.processed_files = set()
        self.processed_files_lock = threading.Lock()
        self.upload_queue = 0
        self.upload_queue_lock = threading.Lock()
        self.is_sleeping = False
        self.enable_notifications = True
        self.enable_autostart = False
        self.only_while_running = False
        self.only_after_closing = False
        self.game_check_active = False
        self.observer = None
        self.game_was_running = None
        self.toaster = ToastNotifier()

    def run(self):
        logging.info("Application starting up...")
        self.setup_config()
        update_autostart_registry(APP_NAME, self.enable_autostart)
        self.load_processed_files()
        self.setup_tray_icon()
        self.start_background_services()
        logging.info("All services started. Running tray icon.")
        self.tray_icon.run()

    def setup_config(self):
        try:
            if not os.path.exists(CONFIG_FILE):
                logging.info("Config file not found. Prompting user for log folder.")
                root = tk.Tk()
                root.withdraw()
                log_folder = filedialog.askdirectory(title="Please select your arcdps log folder")
                if not log_folder:
                    logging.warning("User did not select a folder. Exiting.")
                    sys.exit()
                self.config['Settings'] = {
                    'LogFolder': log_folder,
                    'WebServerPort': '8000',
                    'EnableAutostart': 'false',
                    'EnableNotifications': 'true',
                    'OnlyUploadWhileGameRunning': 'false',
                    'OnlyUploadAfterGameCloses': 'false'
                }
                with open(CONFIG_FILE, 'w') as configfile:
                    self.config.write(configfile)
                logging.info(f"Config saved to {CONFIG_FILE}")
            
            self.config.read(CONFIG_FILE)
            settings = self.config['Settings']
            dirty_config = False
            if 'UploadMode' in settings:
                del settings['UploadMode']
                dirty_config = True
            if not settings.get('EnableAutostart'):
                settings['EnableAutostart'] = 'false'; dirty_config = True
            if not settings.get('EnableNotifications'):
                settings['EnableNotifications'] = 'true'; dirty_config = True
            if not settings.get('OnlyUploadWhileGameRunning'):
                settings['OnlyUploadWhileGameRunning'] = 'false'; dirty_config = True
            if not settings.get('OnlyUploadAfterGameCloses'):
                settings['OnlyUploadAfterGameCloses'] = 'false'; dirty_config = True
            
            if dirty_config:
                 with open(CONFIG_FILE, 'w') as configfile:
                    self.config.write(configfile)
                 logging.info("Updated config file with new default settings.")

            self.folder_to_watch = settings.get('LogFolder')
            self.web_server_port = settings.getint('WebServerPort')
            self.enable_autostart = settings.getboolean('EnableAutostart')
            self.enable_notifications = settings.getboolean('EnableNotifications')
            self.only_while_running = settings.getboolean('OnlyUploadWhileGameRunning')
            self.only_after_closing = settings.getboolean('OnlyUploadAfterGameCloses')
            
            self.game_check_active = self.only_while_running or self.only_after_closing

            logging.info(f"Watching folder: {self.folder_to_watch}")
            logging.info(f"Autostart enabled: {self.enable_autostart}")
            logging.info(f"Notifications enabled: {self.enable_notifications}")
            logging.info(f"Game check active: {self.game_check_active}")

        except Exception as e:
            logging.critical("CRASH in setup_config", exc_info=True)
            raise

    def start_background_services(self):
        self.status.set("PENDING", "Starting services...")
        threading.Thread(target=self.start_web_server, daemon=True).start()
        threading.Thread(target=self.start_file_watcher, daemon=True).start()
        threading.Thread(target=self.periodic_scan_loop, daemon=True).start()

        if self.game_check_active:
            threading.Thread(target=self.initial_game_check_and_start_monitor, daemon=True).start()
        else:
            self.is_sleeping = False
            threading.Thread(target=self.scan_and_upload_existing_logs, daemon=True).start()

    def periodic_scan_loop(self):
        logging.info("Starting periodic backup scanner.")
        while True:
            time.sleep(60)
            if not self.is_sleeping:
                logging.info("Periodic scanner waking up to check for missed files.")
                threading.Thread(target=self.scan_and_upload_existing_logs, args=(False,)).start()

    def initial_game_check_and_start_monitor(self):
        logging.info("Performing initial game check to set state...")
        self.check_game_state_and_update()
        self.game_monitoring_loop()

    def game_monitoring_loop(self):
        logging.info("Starting recurring game monitoring loop.")
        while True:
            time.sleep(30)
            self.check_game_state_and_update()

    def check_game_state_and_update(self):
        try:
            game_is_running = any(proc.name() == GAME_PROCESS_NAME for proc in psutil.process_iter(['name']))

            if self.game_was_running is None or game_is_running != self.game_was_running:
                logging.info(f"Game state change detected. Running: {game_is_running}. Previous: {self.game_was_running}")
                
                can_upload_now = (self.only_while_running and game_is_running) or \
                                 (self.only_after_closing and not game_is_running) or \
                                 (self.only_while_running and self.only_after_closing)

                if can_upload_now:
                    self.is_sleeping = False
                    self.status.set("PENDING", "State changed, waking up...")
                    self.scan_and_upload_existing_logs()
                else:
                    self.is_sleeping = True
                    if self.only_while_running:
                        self.status.set("SLEEPING", f"Waiting for {GAME_PROCESS_NAME}...")
                    elif self.only_after_closing:
                        self.status.set("SLEEPING", "Waiting for you to close GW2...")

            self.game_was_running = game_is_running
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        except Exception as e:
            logging.error("Error in check_game_state_and_update", exc_info=True)

    def menu_factory(self):
        return (
            item(lambda text: self.status.status_text, None, enabled=False),
            item('Visit Log Webpage', self.open_webpage),
            item('Open Log Folder', self.open_log_folder),
            item('Open Config File', self.open_config_file),
            item('Exit', self.exit_app)
        )

    def setup_tray_icon(self):
        icon_path = resource_path(ICON_FILE)
        try:
            image = Image.open(icon_path)
        except FileNotFoundError:
            logging.warning(f"Icon file '{ICON_FILE}' not found. Creating a default icon.")
            width, height = 64, 64
            image = Image.new('RGB', (width, height), "#1a1a1a")
            dc = ImageDraw.Draw(image)
            dc.rectangle([(width // 4, height // 4), (width * 3 // 4, height * 3 // 4)], fill="#3498db")
        
        self.tray_icon = Icon(APP_NAME, image, APP_NAME)
        self.status = AppStatus(self, self.tray_icon)
        self.status.update()

    def open_webpage(self):
        webbrowser.open(f"http://localhost:{self.web_server_port}")

    def open_log_folder(self):
        os.startfile(self.folder_to_watch)

    def open_config_file(self):
        os.startfile(CONFIG_FILE)

    def exit_app(self):
        logging.info("Exit requested. Shutting down...")
        if self.observer:
            self.observer.stop()
            self.observer.join()
        self.tray_icon.stop()

    def load_processed_files(self):
        try:
            if os.path.exists(UPLOADED_LOGS_TRACKER_FILE):
                with open(UPLOADED_LOGS_TRACKER_FILE, 'r') as f:
                    self.processed_files = set(line.strip() for line in f)
                logging.info(f"Loaded {len(self.processed_files)} previously uploaded logs.")
        except Exception as e:
            logging.error("Could not read tracker file", exc_info=True)

    def add_to_processed_files(self, filename):
        with self.processed_files_lock:
            self.processed_files.add(filename)
            try:
                with open(UPLOADED_LOGS_TRACKER_FILE, 'a') as f:
                    f.write(filename + '\n')
            except Exception as e:
                logging.critical("Could not write to tracker file", exc_info=True)

    def handle_log_file(self, file_path):
        if self.is_sleeping: return
        filename = os.path.basename(file_path)
        with self.processed_files_lock:
            if filename in self.processed_files: return
        with self.upload_queue_lock:
            self.upload_queue += 1
        self.upload_log_to_dps_report(file_path, filename)
        with self.upload_queue_lock:
            self.upload_queue -= 1
            if self.upload_queue == 0 and not self.is_sleeping:
                self.status.set("UP TO DATE", "All logs processed.")

    def upload_log_to_dps_report(self, file_path, filename):
        if self.is_sleeping: return
        self.status.set("UPLOADING", f"Processing {filename}...")
        time.sleep(2)
        upload_url = "https://dps.report/uploadContent?json=1&generator=ei"
        try:
            with open(file_path, 'rb') as f:
                files = {'file': (filename, f)}
                response = requests.post(upload_url, files=files, timeout=120)
                response.raise_for_status()
            data = response.json()
            logging.info(f"Successfully uploaded {filename}. URL: {data.get('permalink')}")
            self.add_to_processed_files(filename)
            with self.web_logs_lock:
                self.uploaded_logs_for_web.insert(0, {
                    "permalink": data.get('permalink'),
                    "boss": data.get('encounter', {}).get('boss', 'Unknown'),
                    "success": data.get('encounter', {}).get('success', False),
                    "upload_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
            
            if self.enable_notifications:
                try:
                    boss_name = data.get('encounter', {}).get('boss', 'Unknown')
                    result = "Success" if data.get('encounter', {}).get('success', False) else "Failure"
                    
                    # FIX: Only provide icon_path if not running as a bundled .exe
                    # This prevents the TypeError: WPARAM crash.
                    notification_icon_path = None
                    if not hasattr(sys, '_MEIPASS'):
                        notification_icon_path = resource_path(ICON_FILE)

                    self.toaster.show_toast(
                        "Log Uploaded",
                        f"Boss: {boss_name}\nResult: {result}",
                        icon_path=notification_icon_path,
                        duration=10,
                        threaded=True
                    )
                except Exception as e:
                    logging.error("Failed to show notification", exc_info=True)

        except requests.exceptions.ConnectionError:
            self.status.set("DISCONNECTED", "Connection to dps.report failed.")
        except requests.exceptions.RequestException as e:
            logging.error(f"Error uploading {filename}", exc_info=True)
        except Exception as e:
            logging.error(f"An unexpected error occurred during upload of {filename}", exc_info=True)

    def scan_and_upload_existing_logs(self, set_status=True):
        if self.is_sleeping: return
        if set_status:
            self.status.set("UPLOADING", "Performing initial scan...")
        unprocessed_logs = []
        for root, _, files in os.walk(self.folder_to_watch):
            for file in files:
                if file.endswith(('.evtc', '.zevtc')):
                    with self.processed_files_lock:
                        if file not in self.processed_files:
                            unprocessed_logs.append(os.path.join(root, file))
        if not unprocessed_logs:
            if not self.is_sleeping and set_status:
                self.status.set("UP TO DATE", "All logs processed.")
            return
        total = len(unprocessed_logs)
        for i, file_path in enumerate(unprocessed_logs):
            if self.is_sleeping: break
            if set_status:
                self.status.set("UPLOADING", f"Initial scan... ({i+1}/{total})")
            self.handle_log_file(file_path)
        
        if not self.is_sleeping and set_status:
            self.status.set("UP TO DATE", "Initial scan complete.")

    def start_web_server(self):
        def handler(*args, **kwargs):
            WebDashboardHandler(self, *args, **kwargs)
        try:
            server = HTTPServer(('', self.web_server_port), handler)
            logging.info(f"Web server started at http://localhost:{self.web_server_port}")
            server.serve_forever()
        except Exception as e:
            self.status.set("DISCONNECTED", f"Web server failed: {e}")
            logging.critical("Could not start web server", exc_info=True)

    def clear_web_session(self):
        with self.web_logs_lock:
            self.uploaded_logs_for_web.clear()
        logging.info("Web session cleared.")

    def start_file_watcher(self):
        if not os.path.isdir(self.folder_to_watch):
            self.status.set("DISCONNECTED", "Log folder not found!")
            return
        event_handler = LogUploaderEventHandler(self)
        self.observer = Observer()
        self.observer.schedule(event_handler, self.folder_to_watch, recursive=True)
        self.observer.start()
        logging.info(f"File watcher started for: {self.folder_to_watch}")

class LogUploaderEventHandler(FileSystemEventHandler):
    def __init__(self, app_instance):
        self.app = app_instance

    def on_created(self, event):
        if not self.app.is_sleeping and not event.is_directory and (event.src_path.endswith(('.evtc', '.zevtc'))):
            threading.Thread(target=self.app.handle_log_file, args=(event.src_path,)).start()

class WebDashboardHandler(BaseHTTPRequestHandler):
    def __init__(self, app_instance, *args, **kwargs):
        self.app = app_instance
        BaseHTTPRequestHandler.__init__(self, *args, **kwargs)

    def do_GET(self):
        try:
            if self.path == '/clear':
                self.app.clear_web_session()
                self.send_response(302)
                self.send_header('Location', '/')
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            html = self.get_html_content()
            self.wfile.write(html.encode('utf-8'))
        except Exception as e:
            logging.error("Error handling web request", exc_info=True)
            self.send_error(500, "Internal Server Error")
            self.end_headers()
            self.wfile.write(b"<h1>500 - Internal Server Error</h1><p>Check app_log.txt for details.</p>")

    def log_message(self, format, *args):
        logging.info("%s - %s" % (self.address_string(), format % args))

    def get_html_content(self):
        log_rows = ''
        with self.app.web_logs_lock:
            if not self.app.uploaded_logs_for_web:
                log_rows = '<tr><td colspan="4" style="text-align:center; padding: 20px;">Awaiting new logs...</td></tr>'
            else:
                for log in self.app.uploaded_logs_for_web:
                    status_class = "status-success" if log['success'] else "status-fail"
                    status_text = "Success" if log['success'] else "Fail"
                    log_rows += f"""
                        <tr>
                            <td>{log['boss']}</td>
                            <td class="{status_class}">{status_text}</td>
                            <td>{log['upload_time']}</td>
                            <td><a href="{log['permalink']}" target="_blank">{log['permalink']}</a></td>
                        </tr>
                    """
        return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{APP_NAME}</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #1a1a1a; color: #e0e0e0; margin: 0; padding: 2rem; }}
                .container {{ max-width: 1000px; margin: 0 auto; }}
                h1 {{ color: #eee; border-bottom: 2px solid #444; padding-bottom: 10px; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th, td {{ padding: 12px 15px; text-align: left; border-bottom: 1px solid #333; }}
                th {{ background-color: #2c2c2c; }}
                tr:nth-child(even) {{ background-color: #252525; }}
                a {{ color: #3498db; text-decoration: none; }}
                a:hover {{ text-decoration: underline; }}
                .status-success {{ color: #2ecc71; font-weight: bold; }}
                .status-fail {{ color: #e74c3c; font-weight: bold; }}
                .button {{ background-color: #3498db; color: white; padding: 10px 15px; border: none; border-radius: 5px; cursor: pointer; text-decoration: none; display: inline-block; margin-top: 1rem; }}
                .button:hover {{ background-color: #2980b9; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>{APP_NAME}</h1>
                <p>Watching folder: <code>{self.app.folder_to_watch}</code></p>
                <a href="/clear" class="button">Clear Session View</a>
                <table>
                    <thead><tr><th>Boss</th><th>Encounter Result</th><th>Upload Time</th><th>dps.report Link</th></tr></thead>
                    <tbody>{log_rows}</tbody>
                </table>
            </div>
        </body>
        </html>
        """

if __name__ == "__main__":
    try:
        app = LogUploaderApp()
        app.run()
    except Exception as e:
        logging.critical("UNHANDLED EXCEPTION: The application has crashed.", exc_info=True)
