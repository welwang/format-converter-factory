"""四維八德 core process (swbd-core.exe): the conversion engine without a window.

The C program 四維八德.exe owns the window and starts this process with piped stdin / stdout.
One UTF-8 line per message (see _build/shell/main.c for the full protocol):

    in   Q <json>          a call from the page: {"id": n, "m": "method", "a": [args]}
         A <id>\\t<json>    the window's answer to one of our requests (file dialogs)
         E <json>          {"ev": "files", "paths": [...]}  /  {"ev": "close"}
    out  R <json>          to the page: {"id": n, "ok": true, "r": result} or {"ev": "drop", ...}
         S <id>\\t<op>\\t... window operation (open / folder / save / title / minimize / restore / flash / quit / ready)

Nothing else may write to the protocol pipe, so the real stdout is moved aside first and anything
printed by libraries ends up in logs\\core.log (stderr) instead.
"""
import os, sys, json, threading, itertools
from concurrent.futures import ThreadPoolExecutor


def _protocol_streams():
    """Keep private copies of the pipe handles; point fd 0 / 1 (and the Windows std handles that child
    processes inherit) at NUL / the log so ffmpeg, LibreOffice ... can never read or write the pipe."""
    proto_in = os.fdopen(os.dup(0), 'rb', buffering=65536)
    proto_out = os.fdopen(os.dup(1), 'wb', buffering=0)
    null = os.open(os.devnull, os.O_RDONLY)
    os.dup2(null, 0); os.close(null)
    os.dup2(2, 1)
    if os.name == 'nt':
        import ctypes, msvcrt
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.SetStdHandle.argtypes = (ctypes.c_uint32, ctypes.c_void_p)
        kernel.SetStdHandle.restype = ctypes.c_int
        for standard, fd in ((-10, 0), (-11, 1), (-12, 2)):
            os.set_inheritable(fd, True)
            if not kernel.SetStdHandle(standard & 0xffffffff, msvcrt.get_osfhandle(fd)):
                raise ctypes.WinError(ctypes.get_last_error())
    sys.stdout = sys.stderr
    return proto_in, proto_out


class Window:
    """What the API used to get from pywebview's window object, now carried out by the C program."""

    def __init__(self, send):
        self._send = send
        self._ids = itertools.count(1)
        self._waiting = {}
        self._lock = threading.Lock()

    @staticmethod
    def _clean(text):
        return str(text or '').replace('\t', ' ').replace('\r', ' ').replace('\n', ' ')

    def _op(self, op, *args, wait=False, timeout=None):
        if not wait:
            self._send('S 0\t' + '\t'.join([op] + [self._clean(a) for a in args]))
            return None
        rid = next(self._ids); ev = threading.Event()
        with self._lock: self._waiting[rid] = [ev, None]
        self._send(f'S {rid}\t' + '\t'.join([op] + [self._clean(a) for a in args]))
        ev.wait(timeout)
        with self._lock: return self._waiting.pop(rid, [None, None])[1]

    def answer(self, rid, payload):
        with self._lock:
            slot = self._waiting.get(rid)
            if slot: slot[1] = payload; slot[0].set()

    @staticmethod
    def _filters(file_types):
        # pywebview style '交付配方 (*.json)' -> name \x1f pattern, joined by \x1e
        out = []
        for ft in file_types or ():
            name = str(ft); pat = '*.*'
            if '(' in name and name.endswith(')'): pat = name[name.rindex('(') + 1:-1].strip() or '*.*'
            out.append(Window._clean(name) + '\x1f' + Window._clean(pat))
        return '\x1e'.join(out)

    def create_file_dialog(self, kind='open', allow_multiple=False, file_types=(), save_filename='', directory=''):
        if kind == 'folder': r = self._op('folder', wait=True)
        elif kind == 'save': r = self._op('save', save_filename, self._filters(file_types), wait=True)
        else: r = self._op('open', '1' if allow_multiple else '0', self._filters(file_types), wait=True)
        return r or None          # pywebview returned None when the dialog was cancelled

    def set_title(self, title): self._op('title', title)
    def minimize(self): self._op('minimize')
    def restore(self): self._op('restore')
    def show(self): self._op('front')
    def flash(self): self._op('flash')
    def quit(self): self._op('quit')


def main():
    argv = sys.argv[1:]
    if argv[:1] == ['--pdf-selftest']:
        import pdf_selftest
        return pdf_selftest.main(argv[1] if len(argv) > 1 else '.')
    if argv[:1] == ['--selftest']:
        import selftest
        return selftest.main(argv[1] if len(argv) > 1 else None)

    proto_in, proto_out = _protocol_streams()
    out_lock = threading.Lock()

    def send(line):
        data = (line + '\n').encode('utf-8')
        with out_lock:
            remaining = memoryview(data)
            while remaining:
                written = proto_out.write(remaining)
                if not written: raise BrokenPipeError('背景通訊管線已關閉')
                remaining = remaining[written:]

    def reply(obj):
        send('R ' + json.dumps(obj, ensure_ascii=False, default=str))

    import engine as E
    import app
    win = Window(send)
    api = app.Api(); api._win = win; app.api = api
    api._fin.stop_event.set()     # finish actions, title progress and sleep prevention now live in the C program
    send('S 0\tready')

    pool = ThreadPoolExecutor(max_workers=16, thread_name_prefix='call')

    def call(raw):
        rid = None
        try:
            req = json.loads(raw); rid = req.get('id'); name = req.get('m') or ''
            fn = getattr(api, name, None) if not name.startswith('_') else None
            if not callable(fn): raise AttributeError(f'沒有這個功能：{name}')
            reply(dict(id=rid, ok=True, r=fn(*(req.get('a') or []))))
        except Exception as e:
            if not isinstance(e, (ValueError, RuntimeError, FileNotFoundError, OSError)): E.log(f'call failed: {name if "name" in locals() else "invalid request"}: {type(e).__name__}')
            reply(dict(id=rid, ok=False, e=str(e) or type(e).__name__))

    def files(paths):
        paths = [p for p in paths if isinstance(p, str) and os.path.exists(p)]
        if paths: reply(dict(ev='drop', list=api.describe(paths), paths=paths))

    def close():
        try: api.close()
        finally: win.quit()

    for raw in proto_in:
        line = raw.decode('utf-8', 'replace').rstrip('\r\n')
        kind, body = line[:1], line[2:]
        if kind == 'Q':
            pool.submit(call, body)
        elif kind == 'A':
            rid, _, payload = body.partition('\t')
            try: win.answer(int(rid), json.loads(payload) if payload else None)
            except ValueError: pass
        elif kind == 'E':
            try: ev = json.loads(body)
            except ValueError: continue
            if ev.get('ev') == 'files': pool.submit(files, ev.get('paths') or [])
            elif ev.get('ev') == 'close': pool.submit(close)
    # the window is gone (pipe closed): stop work and save, then leave
    try: api.close()
    except Exception: pass
    os._exit(0)


if __name__ == '__main__':
    sys.exit(main())
