"""Crash-safe writes: publish complete files, never partial PNGs."""
import json
import os
from pathlib import Path
import tempfile


def atomic_write(path, writer, *, replace_existing=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.marble-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            writer(stream)
            stream.flush()
            os.fsync(stream.fileno())
        if replace_existing:
            os.replace(temporary, path)
            return path
        index = 0
        while True:
            candidate = path if not index else path.with_name(f'{path.stem}_{index:03d}{path.suffix}')
            try:
                # Atomic, no-overwrite publication of the completed file.
                os.link(temporary, candidate)
                return candidate
            except FileExistsError:
                index += 1
    finally:
        Path(temporary).unlink(missing_ok=True)


def save_json(path, data, *, replace_existing=False):
    payload = json.dumps(data, indent=2, allow_nan=False).encode('utf-8')
    return atomic_write(path, lambda stream: stream.write(payload), replace_existing=replace_existing)


def save_image(path, image):
    return atomic_write(path, lambda stream: image.save(stream, format='PNG'))
