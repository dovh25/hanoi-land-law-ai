"""Standard-library-only ZIP gate. Never execute code from an unverified archive."""
from pathlib import Path
import shutil
import stat
import tempfile
import zipfile
import os

MAX_FILES = 20005
MAX_BYTES = 256 * 1024 * 1024


def write_member(archive, name, *, path=None, data=None):
    """Stable ZIP metadata: identical input/code yields identical upload bytes."""
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    with archive.open(info, "w") as target:
        if path is not None:
            with Path(path).open("rb") as source: shutil.copyfileobj(source, target, length=128 * 1024)
        else:
            target.write(data)


def safe_root(path):
    path = Path(path)
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("Symlink path refused; choose a regular exchange directory")
    return path


def inspect_zip(source, allowed):
    entries = source.infolist()
    names = [e.filename for e in entries]
    if (not entries or len(entries) > MAX_FILES or len(names) != len(set(names))
            or sum(e.file_size for e in entries) > MAX_BYTES):
        raise ValueError("Archive duplicate/file-count/size limit failed; regenerate a smaller package")
    for entry in entries:
        mode = entry.external_attr >> 16
        name = entry.filename
        if (not allowed(name) or "\\" in name or name.startswith("/") or ".." in Path(name).parts
                or entry.is_dir() or entry.flag_bits & 1
                or (stat.S_IFMT(mode) not in {0, stat.S_IFREG})):
            raise ValueError("Archive has an unexpected/unsafe entry; use only the generated exchange ZIP")
    return names


def extract_zip(archive, destination, allowed):
    archive, destination = safe_root(archive), safe_root(destination)
    if destination.exists(): raise ValueError("Extraction target exists; choose a fresh directory to preserve data")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as source:
        inspect_zip(source, allowed)
        with tempfile.TemporaryDirectory(prefix=".extract-", dir=destination.parent) as temporary:
            stage = Path(temporary) / "package"
            stage.mkdir()
            for entry in source.infolist():
                path = stage / entry.filename
                path.parent.mkdir(parents=True, exist_ok=True)
                with source.open(entry) as src, path.open("xb") as dst:
                    shutil.copyfileobj(src, dst, length=128 * 1024)
            os.rename(stage, destination)
    return destination
