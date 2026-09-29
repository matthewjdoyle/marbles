"""One spawned render at a time, with cancellable previews and stale-result guards."""
from collections import deque
import json
import multiprocessing
from pathlib import Path
import tempfile

from PySide6.QtCore import QObject, QTimer, Signal

from .render import worker, export_worker


class RenderQueue(QObject):
    result = Signal(int, object, object)
    failed = Signal(int, object, str)
    progress = Signal(str)
    busy_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.context = multiprocessing.get_context('spawn')
        self.pending = deque()
        self.active = None
        self.sequence = 0
        self.directory = tempfile.TemporaryDirectory(prefix='marble-studio-')
        self.timer = QTimer(self)
        self.timer.setInterval(40)
        self.timer.timeout.connect(self.poll)
        self.timer.start()

    @property
    def busy(self):
        return bool(self.active or self.pending)

    def submit(self, request):
        self.sequence += 1
        # Snapshot nested recipes before passing them across process boundaries.
        request = json.loads(json.dumps(request, allow_nan=False))
        if request.get('interactive'):
            self.cancel_interactive()
        elif self.active and self.active[1].get('interactive'):
            self._stop_active()
        self.pending.append((self.sequence, request))
        self._start_next()
        return self.sequence

    def cancel_interactive(self):
        self.pending = deque((i, r) for i, r in self.pending if not r.get('interactive'))
        if self.active and self.active[1].get('interactive'):
            self._stop_active()
        self.busy_changed.emit(self.busy)

    def cancel(self):
        self.pending.clear()
        if self.active and self.active[1]['kind'] == 'commit':
            self.progress.emit('Finishing the current file save…')
            return False
        self._stop_active()
        self.busy_changed.emit(False)
        return True

    def _stop_active(self):
        if self.active:
            _, _, process, connection = self.active
            process.terminate()
            process.join(timeout=1)
            if process.is_alive():
                process.kill()
                process.join()
            connection.close()
            process.close()
            self.active = None

    def _start_next(self):
        if self.active or not self.pending:
            self.busy_changed.emit(self.busy)
            return
        job_id, request = self.pending.popleft()
        receiver, sender = self.context.Pipe(duplex=False)
        directory = Path(self.directory.name) / str(job_id)
        directory.mkdir()
        if request['kind'] == 'commit':
            target, args = export_worker, (sender, request['source'], request['target'])
        else:
            target, args = worker, (sender, request, str(directory))
        process = self.context.Process(target=target, args=args, daemon=True)
        try:
            process.start()
        except Exception as error:
            receiver.close()
            sender.close()
            self.failed.emit(job_id, request, str(error))
            self._start_next()
            return
        sender.close()
        self.active = job_id, request, process, receiver
        self.busy_changed.emit(True)

    def poll(self):
        if not self.active:
            return
        job_id, request, process, connection = self.active
        try:
            while connection.poll():
                event, data = connection.recv()
                if event == 'progress':
                    self.progress.emit(data)
                else:
                    self._finish()
                    if event == 'result':
                        self.result.emit(job_id, request, data)
                    else:
                        self.failed.emit(job_id, request, data)
                    self._start_next()
                    return
        except (EOFError, OSError):
            self._finish()
            self.failed.emit(job_id, request, 'Render worker stopped unexpectedly. Try rendering again or use a smaller canvas.')
            self._start_next()
            return
        if not process.is_alive():
            self._finish()
            self.failed.emit(job_id, request, 'Render worker exited without an image. Try a smaller canvas.')
            self._start_next()

    def _finish(self):
        _, _, process, connection = self.active
        process.join(timeout=.1)
        if process.is_alive():
            process.terminate()
            process.join(timeout=1)
        connection.close()
        process.close()
        self.active = None

    def shutdown(self):
        self.timer.stop()
        self.pending.clear()
        self._stop_active()
        self.directory.cleanup()
