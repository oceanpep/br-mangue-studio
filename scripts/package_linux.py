"""Bundle the Linux executable, icon and shortcut instructions for download."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import re
import tarfile
import tempfile
import shutil


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("dist"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    version_match = re.search(r'^version = "([^"]+)"$', (root / "pyproject.toml").read_text(), re.MULTILINE)
    if version_match is None:
        raise ValueError("The project version is missing from pyproject.toml.")
    version = version_match.group(1)
    name = f"BR-MANGUE_Studio-{version}-Linux-x86_64"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="brmangue-linux-package-") as temporary:
        folder = Path(temporary) / name
        folder.mkdir()
        files = {
            "BRMANGUE_Studio_Linux_x86_64": args.executable,
            "BR-MANGUE_BR_icon.png": root / "src/brmangue_studio/assets/BR-MANGUE_BR_icon.png",
            "Install_shortcuts.sh": root / "packaging/linux/Install_shortcuts.sh",
            "README.md": root / "packaging/linux/README.md",
            "LICENSE": root / "LICENSE",
        }
        checksums = []
        for target, source in files.items():
            destination = folder / target
            shutil.copyfile(source, destination)
            destination.chmod(0o755 if target.endswith(".sh") or target == "BRMANGUE_Studio_Linux_x86_64" else 0o644)
            checksums.append(hashlib.sha256(destination.read_bytes()).hexdigest() + "  " + target)
        (folder / "CHECKSUMS.sha256").write_text("\n".join(checksums) + "\n")
        archive = args.output_dir / (name + ".tar.gz")
        with tarfile.open(archive, "w:gz") as package:
            package.add(folder, arcname=name)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_name(archive.name + ".sha256").write_text(digest + "  " + archive.name + "\n")
    print(archive)


if __name__ == "__main__":
    main()
