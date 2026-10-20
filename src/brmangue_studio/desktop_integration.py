"""Optional Linux desktop launchers for a user-owned portable application."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys


DESKTOP_ID = "io.github.oceanpep.BRMangueStudio"
LINUX_WINDOW_CLASS = "Brmanguestudio"


def _desktop_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")


def _desktop_argument(value: str) -> str:
    """Quote one Exec argument using desktop-entry rules, without a shell."""
    escaped = value.replace("%", "%%")
    for character in ("\\", '"', "`", "$"):
        escaped = escaped.replace(character, "\\" + character)
    return _desktop_string('"' + escaped + '"')


def _desktop_directory() -> Path | None:
    command = shutil.which("xdg-user-dir")
    if command:
        try:
            result = subprocess.run(
                [command, "DESKTOP"], capture_output=True, text=True,
                timeout=5, check=False,
            )
            candidate = Path(result.stdout.strip())
            if result.returncode == 0 and candidate.is_absolute() and candidate.is_dir():
                if candidate.resolve() != Path.home().resolve():
                    return candidate
        except (OSError, subprocess.TimeoutExpired):
            pass
    return None


def _optional_desktop_command(arguments: list[str]) -> bool:
    try:
        return subprocess.run(
            arguments, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=5, check=False,
        ).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def create_linux_shortcuts(executable: Path | None = None) -> dict[str, object]:
    """Register launchers for this executable without copying it or using root."""
    if not sys.platform.startswith("linux"):
        raise ValueError("Application shortcuts are available on Linux.")
    if executable is None:
        if not getattr(sys, "frozen", False):
            raise ValueError("Create shortcuts from the packaged Linux executable.")
        executable = Path(sys.executable)
    executable = executable.expanduser().resolve()
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise ValueError("The application executable is missing or is not executable.")
    if any(character in str(executable) for character in ("\n", "\r", "\t", "=")):
        raise ValueError("The application path contains unsupported launcher characters.")

    icon_source = Path(__file__).resolve().parent / "assets" / "BR-MANGUE_BR_icon.png"
    if not icon_source.is_file():
        raise FileNotFoundError("The bundled application icon is missing.")
    data_home = Path(os.environ.get("XDG_DATA_HOME", "")).expanduser()
    if not data_home.is_absolute():
        data_home = Path.home() / ".local" / "share"
    icon = data_home / "brmangue-studio" / "BR-MANGUE_BR_icon.png"
    icon.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(icon_source, icon)

    content = "\n".join((
        "[Desktop Entry]",
        "Type=Application",
        "Name=BR-MANGUE Studio",
        "GenericName=Mangrove simulation",
        "GenericName[pt_BR]=Simulação de manguezais",
        "Comment=Spatial cellular modelling of mangroves",
        "Comment[pt_BR]=Modelagem espacial de manguezais com autômatos celulares",
        "Exec=" + _desktop_argument(str(executable)),
        "Icon=" + _desktop_string(str(icon)),
        "Terminal=false",
        "Categories=Education;Science;",
        "Keywords=Mangrove;Coastal;Simulation;GIS;",
        "StartupNotify=false",
        "StartupWMClass=" + LINUX_WINDOW_CLASS,
        "",
    ))
    applications = data_home / "applications"
    applications.mkdir(parents=True, exist_ok=True)
    menu_entry = applications / (DESKTOP_ID + ".desktop")
    menu_entry.write_text(content, encoding="utf-8")
    menu_entry.chmod(0o755)
    launchers = [menu_entry]
    warnings: list[str] = []
    destinations = [executable.parent / "BR-MANGUE Studio.desktop"]
    desktop = _desktop_directory()
    if desktop is not None:
        destinations.append(desktop / "BR-MANGUE Studio.desktop")
    for target in dict.fromkeys(destinations):
        try:
            target.write_text(content, encoding="utf-8")
            target.chmod(0o755)
            launchers.append(target)
        except OSError:
            warnings.append(str(target))

    gio = shutil.which("gio")
    if gio:
        for launcher in launchers:
            _optional_desktop_command([gio, "set", str(launcher), "metadata::trusted", "true"])
        # File managers such as Nautilus can also display the logo on the ELF.
        _optional_desktop_command([
            gio, "set", str(executable), "metadata::custom-icon", icon.as_uri(),
        ])
    updater = shutil.which("update-desktop-database")
    if updater:
        _optional_desktop_command([updater, str(applications)])
    return {
        "menu_entry": str(menu_entry),
        "launchers": [str(path) for path in launchers],
        "icon": str(icon),
        "unwritable_shortcut_locations": warnings,
    }
