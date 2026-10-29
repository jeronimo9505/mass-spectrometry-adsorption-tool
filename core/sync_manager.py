import os
import subprocess
import threading

DEFAULT_SOURCE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SUPERVISOR_DIR = r"C:\Users\Lenovo\OneDrive - unizar.es\Shayan Ph.D. Student\AI Antigravity software"

def sync_to_supervisor(source_dir=None, target_dir=None, async_mode=True, on_complete=None):
    """
    Synchronizes the current working directory to the Supervisor folder
    shared on OneDrive using Windows robocopy (mirror mode).
    Excludes internal Git history (.git) and bytecode (__pycache__).
    """
    src = source_dir or DEFAULT_SOURCE_DIR
    dst = target_dir or DEFAULT_SUPERVISOR_DIR

    def _run():
        if not os.path.exists(src):
            if on_complete:
                on_complete(False, f"Source directory not found: {src}")
            return False

        try:
            os.makedirs(dst, exist_ok=True)
            cmd = [
                "robocopy",
                src,
                dst,
                "/MIR",
                "/XD", ".git", "__pycache__",
                "/XF", "*.tmp"
            ]
            # In robocopy, exit codes < 8 indicate success (0=no change, 1=copied, 2=extra files, etc.)
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True)
            success = result.returncode < 8
            msg = "Sync completed successfully." if success else f"Sync failed with code {result.returncode}."
            if on_complete:
                on_complete(success, msg)
            return success
        except Exception as e:
            if on_complete:
                on_complete(False, str(e))
            return False

    if async_mode:
        t = threading.Thread(target=_run, daemon=True)
        t.start()
        return t
    else:
        return _run()
