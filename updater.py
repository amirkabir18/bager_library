"""
Multi-layer auto-update system for Bager Library.
Handles metadata loading, version comparison, release checks against GitHub,
resilient chunked streaming downloads with progress tracking, and atomic self-replacement on Windows.
"""

import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)
BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
APP_INFO_PATH = os.path.join(BASE_DIR, "app_info.json")

DEFAULT_APP_INFO = {
    "name": "bager_library",
    "app_name": "کتابخانه باقر العلوم",
    "version": "0.1.0",
    "github_repo": "amirkabir18/bager_library",
    "repository_url": "https://github.com/amirkabir18/bager_library",
    "description": "سیستم مدیریت کتابخانه باقرالعلوم",
}


def load_app_info(filepath: Optional[str] = None) -> dict:
    """
    Loads application info from app_info.json with fallback defaults.
    """
    target = filepath or APP_INFO_PATH
    if os.path.exists(target):
        try:
            with open(target, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    merged = dict(DEFAULT_APP_INFO)
                    merged.update(data)
                    return merged
        except Exception:
            pass
    return dict(DEFAULT_APP_INFO)


def parse_version(version_str: str) -> tuple[int, ...]:
    """
    Extracts numeric version parts as a tuple of ints, e.g. 'v0.1.2' -> (0, 1, 2).
    """
    cleaned = str(version_str).strip().lower().lstrip("v")
    digits = re.findall(r"\d+", cleaned)
    if not digits:
        return (0, 0, 0)
    return tuple(int(d) for d in digits)


def is_newer_version(remote_version: str, local_version: str) -> bool:
    """
    Returns True if remote_version is strictly newer than local_version.
    """
    remote_parts = parse_version(remote_version)
    local_parts = parse_version(local_version)
    max_len = max(len(remote_parts), len(local_parts))
    r_padded = remote_parts + (0,) * (max_len - len(remote_parts))
    l_padded = local_parts + (0,) * (max_len - len(local_parts))
    return r_padded > l_padded


def format_size(num_bytes: int) -> str:
    """
    Formats a byte count into a human-readable string (KB, MB, GB).
    """
    if num_bytes <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB"]
    size = float(num_bytes)
    unit_idx = 0
    while size >= 1024.0 and unit_idx < len(units) - 1:
        size /= 1024.0
        unit_idx += 1
    return f"{size:.1f} {units[unit_idx]}"


def format_speed(bytes_per_sec: float) -> str:
    """
    Formats speed in bytes per second to human-readable string.
    """
    return f"{format_size(int(bytes_per_sec))}/s"


class UpdateChecker:
    """
    Queries GitHub Releases API to detect available updates,
    with a multi-layer fallback to raw repository app_info.json.
    """

    def __init__(self, repo: Optional[str] = None, current_version: Optional[str] = None):
        info = load_app_info()
        self.repo = repo or info.get("github_repo", "amirkabir18/bager_library")
        self.current_version = current_version or info.get("version", "0.1.0")

    def check(self, timeout: int = 6) -> dict:
        """
        Checks for newer release on GitHub.
        Returns a dict with update details or raises an Exception if check failed.
        """
        api_url = f"https://api.github.com/repos/{self.repo}/releases/latest"
        req = urllib.request.Request(
            api_url,
            headers={
                "User-Agent": f"BagerLibrary-Updater/{self.current_version}",
                "Accept": "application/vnd.github.v3+json",
            },
        )

        release_data = None
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    release_data = json.loads(resp.read().decode("utf-8"))
        except Exception:
            # Fallback layer: try raw app_info.json if releases API is rate limited or unavailable
            release_data = self._check_raw_fallback(timeout=timeout)

        if not release_data:
            raise RuntimeError("امکان برقراری ارتباط با سرور بروزرسانی وجود ندارد.")

        tag_name = release_data.get("tag_name", "")
        remote_version = tag_name.lstrip("v") if tag_name else release_data.get("version", "")
        update_available = is_newer_version(remote_version, self.current_version)

        download_url = None
        asset_name = None
        asset_size = 0

        assets = release_data.get("assets", [])
        for asset in assets:
            name = asset.get("name", "")
            if name.lower().endswith(".exe"):
                download_url = asset.get("browser_download_url")
                asset_name = name
                asset_size = asset.get("size", 0)
                break

        if not download_url and update_available:
            download_url = f"https://github.com/{self.repo}/releases/download/v{remote_version}/bager_library.exe"
            asset_name = "bager_library.exe"

        return {
            "update_available": update_available,
            "latest_version": remote_version,
            "current_version": self.current_version,
            "release_name": release_data.get("name") or f"نسخه {remote_version}",
            "release_notes": release_data.get("body", ""),
            "release_url": release_data.get("html_url") or f"https://github.com/{self.repo}/releases",
            "download_url": download_url,
            "asset_name": asset_name,
            "asset_size": asset_size,
        }

    def _check_raw_fallback(self, timeout: int = 6) -> Optional[dict]:
        raw_url = f"https://raw.githubusercontent.com/{self.repo}/main/app_info.json"
        try:
            req = urllib.request.Request(
                raw_url,
                headers={"User-Agent": f"BagerLibrary-Updater/{self.current_version}"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    v = data.get("version", "")
                    return {
                        "tag_name": f"v{v}",
                        "version": v,
                        "name": f"Release v{v}",
                        "body": "",
                        "html_url": f"https://github.com/{self.repo}/releases",
                        "assets": [],
                    }
        except Exception:
            return None
        return None


class DownloadManager:
    """
    Multi-layer chunked streaming download manager.
    Operates in a background thread with progress reporting, speed calculation,
    cancellation support, and atomic temporary-file validation.
    """

    def __init__(self, chunk_size: int = 65536):
        self.chunk_size = chunk_size
        self._thread: Optional[threading.Thread] = None
        self._cancel_event = threading.Event()
        self._is_downloading = False
        self._temp_file_path: Optional[str] = None

    @property
    def is_downloading(self) -> bool:
        return self._is_downloading

    def cancel(self):
        """Signals download cancellation."""
        self._cancel_event.set()

    def download_async(
        self,
        url: str,
        dest_path: str,
        on_progress: Optional[Callable[[int, int, float, float], Any]] = None,
        on_finished: Optional[Callable[[str], Any]] = None,
        on_error: Optional[Callable[[str], Any]] = None,
        on_cancelled: Optional[Callable[[], Any]] = None,
    ):
        """
        Starts downloading asynchronously in a worker thread.
        on_progress(downloaded_bytes, total_bytes, percentage, speed_bps)
        on_finished(dest_path)
        on_error(error_message)
        on_cancelled()
        """
        if self._is_downloading:
            if on_error:
                on_error("دانلود دیگری در حال انجام است.")
            return

        self._cancel_event.clear()
        self._is_downloading = True

        def _worker():
            tmp_path = dest_path + ".tmp"
            self._temp_file_path = tmp_path
            try:
                dest_dir = os.path.dirname(os.path.abspath(dest_path))
                if not os.path.exists(dest_dir):
                    os.makedirs(dest_dir, exist_ok=True)

                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "BagerLibrary-Downloader"},
                )

                start_time = time.time()
                last_time = start_time
                last_downloaded = 0
                downloaded_bytes = 0
                speed_bps = 0.0

                with urllib.request.urlopen(req, timeout=30) as resp:
                    total_bytes = int(resp.headers.get("Content-Length", 0))

                    with open(tmp_path, "wb") as out_f:
                        while True:
                            if self._cancel_event.is_set():
                                out_f.close()
                                if os.path.exists(tmp_path):
                                    try:
                                        os.remove(tmp_path)
                                    except Exception:
                                        pass
                                self._is_downloading = False
                                if on_cancelled:
                                    on_cancelled()
                                return

                            chunk = resp.read(self.chunk_size)
                            if not chunk:
                                break

                            out_f.write(chunk)
                            downloaded_bytes += len(chunk)

                            now = time.time()
                            elapsed_interval = now - last_time
                            if elapsed_interval >= 0.2:
                                speed_bps = (downloaded_bytes - last_downloaded) / elapsed_interval
                                last_time = now
                                last_downloaded = downloaded_bytes

                                pct = (downloaded_bytes / total_bytes * 100.0) if total_bytes > 0 else 0.0
                                if on_progress:
                                    on_progress(downloaded_bytes, total_bytes, pct, speed_bps)

                if total_bytes > 0 and downloaded_bytes < total_bytes:
                    raise IOError("فایل به صورت ناقص دریافت شد.")

                if os.path.exists(dest_path):
                    try:
                        os.remove(dest_path)
                    except Exception:
                        pass

                os.replace(tmp_path, dest_path)
                self._is_downloading = False

                if on_progress:
                    on_progress(downloaded_bytes, downloaded_bytes, 100.0, 0.0)
                if on_finished:
                    on_finished(dest_path)

            except Exception as e:
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
                self._is_downloading = False
                if on_error:
                    on_error(str(e))

        self._thread = threading.Thread(target=_worker, daemon=True)
        self._thread.start()


def apply_update(new_binary_path: str, target_exe: Optional[str] = None) -> bool:
    """
    Applies the downloaded update for a Windows production environment.

    Launches a detached Windows helper batch script that:
    1. Waits for the current process PID to terminate.
    2. Safely backs up the existing executable (.old).
    3. Swaps in the new binary.
    4. Relaunches the application with its original arguments.

    Returns True if the update mechanism was successfully triggered.
    Returns False if running in an un-frozen (development) environment or not on Windows.
    """
    is_frozen = getattr(sys, "frozen", False)
    current_exe = target_exe or sys.executable

    # In development mode, do not overwrite the python interpreter or source files
    if not is_frozen:
        logger.info("Running in development mode. Skipping self-replacement.")
        return False

    if sys.platform != "win32":
        logger.warning("Auto-update via batch script is only supported on Windows.")
        return False

    if not os.path.exists(new_binary_path):
        raise FileNotFoundError(f"Update file not found: {new_binary_path}")

    if not os.path.exists(current_exe):
        raise FileNotFoundError(f"Current executable not found: {current_exe}")

    # Ensure absolute paths to avoid working directory issues
    new_binary_path = os.path.abspath(new_binary_path)
    current_exe = os.path.abspath(current_exe)

    # Verify write permissions to the target directory before attempting file operations
    target_dir = os.path.dirname(current_exe)
    test_file = os.path.join(target_dir, ".write_test")
    try:
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
    except OSError as e:
        raise PermissionError(
            f"No write permission to target directory: {target_dir}. "
            "Ensure the app is not installed in a read-only location (e.g., Program Files without Admin rights)."
        ) from e

    helper_path = os.path.join(tempfile.gettempdir(), "bager_update_helper.bat")
    pid = os.getpid()

    # Construct the batch script with delayed expansion for safe path handling
    bat_content = f"""@echo off
chcp 65001 > nul
set "PID={pid}"
set "NEW_FILE={new_binary_path}"
set "TARGET_FILE={current_exe}"
set "BACKUP_FILE={current_exe}.old"

setlocal EnableDelayedExpansion

:: Wait for target process to terminate using native process wait
powershell.exe -NoProfile -NonInteractive -Command "try {{ (Get-Process -Id %PID% -ErrorAction Stop).WaitForExit(30000) }} catch {{}}; exit 0" >nul 2>&1
timeout /t 1 /nobreak > nul

if exist "!TARGET_FILE!" (
    move /y "!TARGET_FILE!" "!BACKUP_FILE!" > nul
    if errorlevel 1 (
        echo ERROR: Failed to backup executable. Aborting.
        exit /b 1
    )
)

move /y "!NEW_FILE!" "!TARGET_FILE!" > nul
if errorlevel 1 (
    echo ERROR: Failed to install update. Restoring backup.
    if exist "!BACKUP_FILE!" (
        move /y "!BACKUP_FILE!" "!TARGET_FILE!" > nul
    )
    exit /b 1
)

if exist "!BACKUP_FILE!" (
    del "!BACKUP_FILE!" > nul 2>&1
)

:: Clear PyInstaller environment variables and signal clean process start
set "PYINSTALLER_RESET_ENVIRONMENT=1"
set "_PYI_PARENT_PROCESS_LEVEL="
set "_PYI_ARCHIVE_FILE="
set "_PYI_APPLICATION_HOME_DIR="
set "_PYI_SPLASH_IPC="
set "_MEIPASS2="
set "_MEIPASS="

:: Relaunch with original arguments (%* passes all arguments received by this batch script)
start "" "!TARGET_FILE!" %*

:: Self-delete the helper script
(goto) 2>nul & del "%~f0"
"""

    try:
        with open(helper_path, "w", encoding="utf-8") as f:
            f.write(bat_content)
    except OSError as e:
        raise RuntimeError(f"Failed to write update helper script: {e}") from e

    # Flags to hide the command prompt window
    CREATE_NO_WINDOW = 0x08000000

    startupinfo = None
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0  # SW_HIDE

    # Prepare clean environment to prevent PyInstaller parent process security validation errors
    env = os.environ.copy()
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    for pyi_var in (
        "_PYI_PARENT_PROCESS_LEVEL",
        "_PYI_ARCHIVE_FILE",
        "_PYI_APPLICATION_HOME_DIR",
        "_PYI_SPLASH_IPC",
        "_MEIPASS2",
        "_MEIPASS",
    ):
        env.pop(pyi_var, None)

    # Pass original arguments to the helper script
    cmd = ["cmd.exe", "/c", helper_path] + sys.argv[1:]

    try:
        subprocess.Popen(
            cmd,
            creationflags=CREATE_NO_WINDOW,
            startupinfo=startupinfo,
            env=env,
            close_fds=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info("Windows update helper launched. Application will restart.")
        return True
    except Exception as e:
        raise RuntimeError(f"Failed to launch update helper: {e}") from e
