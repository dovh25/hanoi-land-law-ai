"""Create root .env once, without printing secrets or replacing existing values."""
import os
from pathlib import Path
import secrets

ROOT = Path(__file__).resolve().parents[1]


def create_env(root: Path = ROOT) -> bool:
    target = root / ".env"
    content = (root / ".env.example").read_text(encoding="utf-8")
    content = content.replace("replace-with-a-locally-generated-secret", secrets.token_urlsafe(48))
    try:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(content)
    return True


if __name__ == "__main__":
    print("Created root .env (mode 0600)." if create_env() else "Existing .env preserved unchanged.")
