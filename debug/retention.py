"""Bound disposable diagnostics while preserving live OCR and recovery evidence.

The budget is deliberately soft for pending payments/rounds and files that may
still be OCR inputs. Rotating diagnostic JPEGs are safe to evict immediately.
"""
import json
import re
import threading
import time
from pathlib import Path

DEFAULT_MAX_BYTES = 32 * 1024 * 1024
MAX_LOG_BYTES = 256 * 1024
PRUNE_INTERVAL = 60
OCR_GRACE_SECONDS = 600
_last = {}
_lock = threading.Lock()
_DIAGNOSTIC_SUFFIXES = {'.png', '.jpg', '.jpeg', '.json', '.jsonl', '.log', '.txt'}
_AUTOMATIC_FOLDERS = {'ui', 'runs', 'trials', 'navigation', 'dock', 'tours', 'missions', 'quests'}


def _within(path, root):
    try:
        resolved = path.resolve()
        return resolved if resolved.is_relative_to(root) else None
    except (OSError, ValueError):
        return None


def _read_json(path):
    if path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError('Recovery record too large to inspect safely')
    return json.loads(path.read_text(encoding='utf-8-sig'))


def _recovery_paths(root):
    """Only runtime records decide whether old diagnostic evidence is pending."""
    protected, active = set(), set()
    runtime = root.parent / 'runtime'
    for record in runtime.glob('*.json'):
        try:
            data = _read_json(record)
        except (OSError, ValueError):
            if record.name == 'mission.json':
                protected.add(root / 'missions')
            continue
        if not isinstance(data, dict):
            continue
        output = data.get('log')
        if isinstance(output, str):
            folder = Path(output)
            if not folder.is_absolute():
                folder = root.parent / folder
            folder = _within(folder, root)
            if folder is not None:
                if data.get('status') in ('NEW', 'RUNNING', 'PAUSED') or data.get('preparing'):
                    active.add(folder)
                if data.get('purchase_pending'):
                    protected.add(folder)
        pending = data.get('pending_round')
        if isinstance(pending, dict) and isinstance(pending.get('path'), str):
            folder = Path(pending['path'])
            if not folder.is_absolute():
                folder = root.parent / folder
            folder = _within(folder, root)
            if folder is not None:
                protected.add(folder)
        if data.get('purchase_pending'):
            # The compact inventory record has no original receipt path.
            # Keep its evidence until the uncertain payment is reconciled.
            protected.add(root / ('missions' if record.name == 'mission.json' else 'ui'))
        if data.get('status') in ('NEW', 'RUNNING', 'PAUSED') and record.name == 'mission.json':
            active.add(root / 'missions')
    return protected, active


def _completed_result(path, root):
    relative = path.relative_to(root)
    # CLI mission ledgers can use a custom state path outside runtime. Their
    # tiny result records remain recovery evidence; GUI results are disposable.
    if len(relative.parts) < 2 or relative.parts[0] not in _AUTOMATIC_FOLDERS - {'missions'}:
        return False
    try:
        data = _read_json(path)
    except (OSError, ValueError):
        return False
    return (isinstance(data, dict) and isinstance(data.get('outcome'), str)
            and all(type(data.get(key)) is int for key in ('casts', 'drags', 'confirmed')))


def _trim_log(path, size, max_bytes):
    """Keep complete recent lines; never load a large historical log into RAM."""
    if size <= max_bytes:
        return size
    temporary = path.with_name(path.name + '.retention.tmp')
    try:
        before = path.stat()
        if before.st_nlink > 1:
            return size
        with path.open('rb') as stream:
            stream.seek(max(0, size - max_bytes))
            tail = stream.read(max_bytes)
        first = tail.find(b'\n')
        tail = tail[first + 1:] if first >= 0 else b''
        last = tail.rfind(b'\n')
        tail = tail[:last + 1] if last >= 0 else b''
        current = path.stat()
        if (current.st_size, current.st_mtime_ns) != (before.st_size, before.st_mtime_ns):
            return current.st_size
        temporary.write_bytes(tail)
        temporary.replace(path)
        return len(tail)
    except OSError:
        return size
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def prune(root, max_bytes=DEFAULT_MAX_BYTES, max_age=86400, now=None,
          protected_paths=(), keep_directories=(), max_log_bytes=MAX_LOG_BYTES):
    root = Path(root).resolve()
    if root.name != 'debug':
        raise ValueError('Retention is restricted to a debug directory')
    now = time.time() if now is None else now
    protected, active = _recovery_paths(root)
    protected.update(p for item in protected_paths if (p := _within(Path(item), root)) is not None)
    active.update(p for item in keep_directories if (p := _within(Path(item), root)) is not None)
    files, directories = [], []
    for path in root.rglob('*'):
        if path.is_symlink() or _within(path, root) is None:
            continue
        relative = path.relative_to(root)
        if any(part in ('__pycache__', 'assets', 'templates', 'fixtures', 'runtime') for part in relative.parts):
            continue
        try:
            stat = path.stat()
            if path.is_dir():
                directories.append((path, stat.st_mtime))
                continue
            if path.suffix.lower() not in _DIAGNOSTIC_SUFFIXES:
                continue
            if any(path == item or path.is_relative_to(item) for item in protected):
                continue
            completed = path.name == 'result.json' and _completed_result(path, root)
            if path.name == 'result.json' and not completed:
                continue
            size = stat.st_size
            if path.suffix.lower() in ('.jsonl', '.log'):
                size = _trim_log(path, size, max_log_bytes)
            rotating_frame = re.fullmatch(r'frame_[012]\.jpg', path.name) is not None
            automatic = bool(relative.parts and relative.parts[0] in _AUTOMATIC_FOLDERS)
            files.append((stat.st_mtime, size, path, completed or (rotating_frame and automatic)))
        except OSError:
            pass
    total = sum(row[1] for row in files)
    for modified, size, path, disposable in sorted(files):
        if not disposable and now - modified < OCR_GRACE_SECONDS:
            continue
        if now - modified <= max_age and total <= max_bytes:
            continue
        try:
            path.unlink()
            total -= size
        except OSError:
            pass
    for path, modified in sorted(directories, key=lambda row: len(row[0].parts), reverse=True):
        # GUI workers publish their active output directory. Standalone CLI
        # controllers may retain an empty travel directory without a ledger.
        if path.relative_to(root).parts[0] != 'ui':
            continue
        if now - modified < OCR_GRACE_SECONDS:
            continue
        if any(path == item or path.is_relative_to(item) or item.is_relative_to(path)
               for item in protected | active):
            continue
        try:
            path.rmdir()  # Only empty directories; never recursive removal.
        except OSError:
            pass
    return total


def maybe_prune(root, *, force=False, protected_paths=(), keep_directories=()):
    """Cheap throttled hook for startup, diagnostic writes and worker shutdown."""
    key = str(Path(root).resolve())
    now = time.monotonic()
    if not force and now - _last.get(key, -10000) < PRUNE_INTERVAL:
        return None
    if not _lock.acquire(blocking=False):
        return None
    try:
        if not force and now - _last.get(key, -10000) < PRUNE_INTERVAL:
            return None
        _last[key] = now
        return prune(root, protected_paths=protected_paths, keep_directories=keep_directories)
    except OSError:
        # A diagnostic retention failure must not abort fishing or payments.
        return None
    finally:
        _lock.release()
