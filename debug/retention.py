"""Bound disposable diagnostics while preserving live OCR and recovery evidence.

The budget is deliberately soft for pending payments/rounds and files that may
still be OCR inputs. Rotating diagnostic JPEGs are safe to evict immediately.
"""
import json
import os
import re
import threading
import time
from pathlib import Path

DEFAULT_MAX_BYTES = 32 * 1024 * 1024
MAX_LOG_BYTES = 256 * 1024
MAX_GUI_REPORTS = 128
MAX_RECORD_BYTES = 4 * 1024 * 1024
PRUNE_INTERVAL = 60
OCR_GRACE_SECONDS = 600
_last = {}
_lock = threading.Lock()
_snapshots = {}
_DIAGNOSTIC_SUFFIXES = {'.png', '.jpg', '.jpeg', '.json', '.jsonl', '.log', '.txt'}
_AUTOMATIC_FOLDERS = {'ui', 'runs', 'trials', 'navigation', 'dock', 'tours', 'missions', 'quests'}


def _within(path, root):
    try:
        resolved = path.resolve()
        return resolved if resolved.is_relative_to(root) else None
    except (OSError, ValueError):
        return None


def _read_json(path):
    with path.open('rb') as stream:
        size = os.fstat(stream.fileno()).st_size
        if size > MAX_RECORD_BYTES:
            raise ValueError('Recovery record too large to inspect safely')
        payload = stream.read(min(size + 1, MAX_RECORD_BYTES + 1))
    if len(payload) > MAX_RECORD_BYTES:
        raise ValueError('Recovery record too large to inspect safely')
    return json.loads(payload.decode('utf-8-sig'))


def _recovery_paths(root):
    """Only runtime records decide whether old diagnostic evidence is pending."""
    protected, active = set(), set()
    runtime = root.parent / 'runtime'
    # Historical runtime backups can contain an obsolete pending flag.
    for name in ('mission.json', 'ui_last.json', 'ui_inventory.json', 'dock.json'):
        record = runtime / name
        if not record.exists():
            continue
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


def _entries(root):
    """Scan once without resolving every deep path or following reparse points."""
    folders = [root]
    while folders:
        folder = folders.pop()
        try:
            with os.scandir(folder) as entries:
                for entry in entries:
                    try:
                        stat = entry.stat(follow_symlinks=False)
                        # Windows junctions must be excluded as well as links.
                        if entry.is_symlink() or getattr(stat, 'st_file_attributes', 0) & 0x400:
                            continue
                        path = Path(entry.path)
                        directory = entry.is_dir(follow_symlinks=False)
                        if entry.name in ('__pycache__', 'assets', 'templates', 'fixtures', 'runtime'):
                            continue
                        yield path, stat, directory
                        if directory:
                            folders.append(path)
                    except OSError:
                        continue
        except OSError:
            continue


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


def _in_reports(path, root, reports):
    parts = path.relative_to(root).parts
    return len(parts) >= 3 and root.joinpath(*parts[:3]) in reports


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
          protected_paths=(), keep_directories=(), max_log_bytes=MAX_LOG_BYTES,
          max_reports=MAX_GUI_REPORTS, recovery_provider=None):
    root = Path(root).resolve()
    if root.name != 'debug':
        raise ValueError('Retention is restricted to a debug directory')
    now = time.time() if now is None else now
    recover = recovery_provider or (lambda: _recovery_paths(root))
    current_protected, current_active = recover()
    protected, active = set(current_protected), set(current_active)
    protected.update(p for item in protected_paths if (p := _within(Path(item), root)) is not None)
    active.update(p for item in keep_directories if (p := _within(Path(item), root)) is not None)
    files, directories, reports = [], [], {}
    for path, stat, directory in _entries(root):
        relative = path.relative_to(root)
        try:
            if directory:
                directories.append((path, stat.st_mtime))
                continue
            if path.suffix.lower() not in _DIAGNOSTIC_SUFFIXES:
                continue
            if any(path == item or path.is_relative_to(item) for item in protected):
                continue
            completed = path.name == 'result.json' and _completed_result(path, root)
            if path.name == 'result.json' and not completed:
                continue
            if (completed and len(relative.parts) >= 4 and relative.parts[0] == 'ui'
                    and re.fullmatch(r'round_\d+', relative.parts[2])):
                report = root.joinpath(*relative.parts[:3])
                reports[report] = max(reports.get(report, 0), stat.st_mtime)
            size = stat.st_size
            if path.suffix.lower() in ('.jsonl', '.log'):
                size = _trim_log(path, size, max_log_bytes)
            rotating_frame = re.fullmatch(r'frame_[012]\.jpg', path.name) is not None
            automatic = bool(relative.parts and relative.parts[0] in _AUTOMATIC_FOLDERS)
            files.append((stat.st_mtime, size, path, completed or (rotating_frame and automatic), stat.st_mtime_ns))
        except OSError:
            pass
    # Background scans can overlap a newly started purchase or a worker switch.
    latest_protected, latest_active = recover()
    protected.update(latest_protected)
    active.update(latest_active)
    files = [row for row in files if not any(row[2] == item or row[2].is_relative_to(item)
                                            for item in protected)]
    total = sum(row[1] for row in files)
    obsolete_reports = set()
    if max_reports is not None:
        obsolete_reports = set(sorted(reports, key=reports.get, reverse=True)[max_reports:])
    for modified, size, path, disposable, modified_ns in sorted(files):
        obsolete = _in_reports(path, root, obsolete_reports)
        if not disposable and not obsolete and now - modified < OCR_GRACE_SECONDS:
            continue
        if not obsolete and now - modified <= max_age and total <= max_bytes:
            continue
        try:
            live_protected = recover()[0] if recovery_provider is not None else protected
            if any(path == item or path.is_relative_to(item) for item in live_protected):
                continue
            current = path.stat()
            if (current.st_mtime_ns, current.st_size) != (modified_ns, size):
                continue  # A live controller refreshed this path during scan.
            path.unlink()
            total -= size
        except OSError:
            pass
    for path, modified in sorted(directories, key=lambda row: len(row[0].parts), reverse=True):
        # GUI workers publish their active output directory. Standalone CLI
        # controllers may retain an empty travel directory without a ledger.
        if path.relative_to(root).parts[0] != 'ui':
            continue
        obsolete = _in_reports(path, root, obsolete_reports)
        if not obsolete and now - modified < OCR_GRACE_SECONDS:
            continue
        if any(path == item or path.is_relative_to(item) or item.is_relative_to(path)
               for item in protected | (set() if obsolete else active)):
            continue
        try:
            path.rmdir()  # Only empty directories; never recursive removal.
        except OSError:
            pass
    return total


def maybe_prune(root, *, force=False, protected_paths=(), keep_directories=(), background=True):
    """Cheap throttled hook for startup, diagnostic writes and worker shutdown."""
    root = Path(root).resolve()
    key = str(root)
    extra_protected = frozenset(p for item in protected_paths if (p := _within(Path(item), root)) is not None)
    extra_active = frozenset(p for item in keep_directories if (p := _within(Path(item), root)) is not None)
    snapshot = _snapshots.get(key)
    if snapshot is not None:
        old_protected, old_active = snapshot[0]
        snapshot[0] = (old_protected | extra_protected, old_active | extra_active)
    now = time.monotonic()
    gate, history = _lock, _last
    if not force and now - history.get(key, -10000) < PRUNE_INTERVAL:
        return None
    if not gate.acquire(blocking=False):
        return None
    if not force and now - history.get(key, -10000) < PRUNE_INTERVAL:
        gate.release()
        return None
    history[key] = now
    cleanup = prune
    try:
        # This caller is the GUI/worker lifecycle thread, before its next atomic
        # state write. A background sweep must never hold runtime file handles:
        # Windows can reject replacement even for a FILE_SHARE_DELETE reader.
        protected, active = _recovery_paths(root)
        snapshot = [(frozenset(protected) | extra_protected, frozenset(active) | extra_active)]
        _snapshots[key] = snapshot
        if len(_snapshots) > 32:
            _snapshots.pop(next(iter(_snapshots)))
    except Exception:
        gate.release()
        return None

    def clean():
        try:
            return cleanup(root, protected_paths=protected_paths, keep_directories=keep_directories,
                           recovery_provider=lambda: snapshot[0])
        except Exception:
            # A diagnostic retention failure must not abort fishing/payments.
            return None
        finally:
            gate.release()

    if background and not force:
        try:
            threading.Thread(target=clean, name='diagnostic-retention', daemon=True).start()
        except RuntimeError:
            gate.release()
        return None
    return clean()
