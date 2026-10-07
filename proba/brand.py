"""Visible product names. Flavor chooses which one the window shows."""

from proba.flavor import (
    ATLAS_APP_NAME,
    ATLAS_EXE_FILE,
    TUTOR_APP_NAME,
    TUTOR_EXE_FILE,
    app_name,
    exe_file,
)

APP_NAME = TUTOR_APP_NAME
EXE_FILE = TUTOR_EXE_FILE
ATLAS_NAME = ATLAS_APP_NAME
ATLAS_EXE = ATLAS_EXE_FILE
OLD_EXE_FILES = ("Проба.exe", "日本語学習アシスタント.exe")


def live_name() -> str:
    return app_name()


def live_exe() -> str:
    return exe_file()
