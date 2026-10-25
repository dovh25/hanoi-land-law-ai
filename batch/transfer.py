"""Data-only archives and an explicit code-only bundle. Never bundle the repository/env."""
from pathlib import Path
import re
import zipfile

from batch.files import validate_input, checked_file


def allowed(name, kind):
    if Path(name).name != name:
        return False
    if kind == "input":
        return name in {"input.json", "records.jsonl"}
    return name == "output.json" or bool(re.fullmatch(r"(?:shard-[0-9]{5}\.json|vectors-[0-9]{5}\.npy)", name))


def pack_transfer(directory, archive, kind):
    directory, archive = Path(directory), Path(archive)
    if kind == "input":
        validate_input(directory)
    names = sorted(path.name for path in directory.iterdir() if allowed(path.name, kind))
    if not names:
        raise ValueError("No transfer files")
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as output:
        for name in names:
            output.write(checked_file(directory, name), name)
    return archive


def unpack_transfer(archive, destination, kind):
    from batch.archive import extract_zip
    destination = extract_zip(archive, destination, lambda name: allowed(name, kind))
    if kind == "input":
        validate_input(destination)
    return destination


def bundle_code(archive):
    root = Path(__file__).resolve().parents[1]
    # Only the credential-free compute package and explicit runtime requirements.
    names = ["__init__.py", "contracts.py", "files.py", "embedding.py", "worker.py", "transfer.py", "rerank.py", "smoke.py", "archive.py"]
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as output:
        for name in names:
            output.write(root / "batch" / name, "batch/" + name)
        output.write(root / "notebooks/colab-requirements.txt", "colab-requirements.txt")
        output.write(root / "LICENSE", "LICENSE")
    return Path(archive)
