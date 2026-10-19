"""Application identity shared by the GUI and Windows shell."""
import ctypes
import sys
from pathlib import Path

APP_NAME = 'Avatools 3x'
APP_VERSION = '2.0.0'
APP_ID = 'Avatools.3x'
ICON_PATH = Path(__file__).resolve().parent / 'assets' / 'avatools.ico'


def apply_identity(root):
    if sys.platform == 'win32':
        shell = ctypes.WinDLL('shell32')
        shell.SetCurrentProcessExplicitAppUserModelID.argtypes = [ctypes.c_wchar_p]
        shell.SetCurrentProcessExplicitAppUserModelID.restype = ctypes.c_long
        shell.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    root.title(APP_NAME)
    root.iconbitmap(default=str(ICON_PATH))
