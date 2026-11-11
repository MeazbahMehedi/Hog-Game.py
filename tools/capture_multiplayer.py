"""Capture actual multiplayer windows over a real temporary loopback relay.

Optional capture dependency: Pillow. No user data or credentials are saved.
"""

from pathlib import Path
import sys
import subprocess
import threading
import time
import ctypes
import ctypes.util
from PIL import ImageGrab

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from hog import GameSession, VERSION, seeded_dice
from hog_desktop import HogApp, tk
from hog_preferences import Preferences
from hog_online import Rooms
from hog_online_client import OnlineClient
from hog_server import RelayServer

def capture(root, name, target=None):
    # Force a fresh mapping before capture on window-manager-free displays.
    root.withdraw()
    root.update()
    root.deiconify()
    root.update()
    def expose(widget):
        if "background" in widget.keys():
            widget.configure(background=widget.cget("background"))
        widget.event_generate("<Expose>")
        for child in widget.winfo_children():
            expose(child)
    expose(root)
    root.update()
    (target or root).deiconify()
    (target or root).lift()
    expose(target or root)
    root.update()
    root.after(180, root.quit)
    root.mainloop()
    root.update()
    target = target or root
    expose(target)
    root.update()
    if sys.platform.startswith('linux'):
        # Real X exposure events refresh Tk backing pixels after transient-window
        # remapping on a virtual display without a window manager.
        x11 = ctypes.CDLL(ctypes.util.find_library('X11'))
        x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XClearArea.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_int, ctypes.c_uint, ctypes.c_uint, ctypes.c_int]
        x11.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
        x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        display = x11.XOpenDisplay(None)
        if display:
            def clear(widget):
                if widget.winfo_viewable():
                    x11.XClearArea(display, widget.winfo_id(), 0, 0, 0, 0, 1)
                for child in widget.winfo_children():
                    clear(child)
            clear(target)
            x11.XSync(display, 0)
            root.update()
            x11.XSync(display, 0)
            root.update()
            x11.XCloseDisplay(display)
    labels = []
    def collect_labels(widget):
        if widget.winfo_class() == 'Label' and widget.winfo_viewable():
            labels.append((widget, widget.cget('text')))
        for child in widget.winfo_children():
            collect_labels(child)
    collect_labels(target)
    for widget, _text in labels:
        widget.configure(text=' ')
    root.update()
    for widget, text in labels:
        widget.configure(text=text)
    root.update()
    target.winfo_pointerxy()
    x, y = target.winfo_rootx(), target.winfo_rooty()
    path = ROOT / 'docs/screenshots' / f'v{VERSION}-{name}.png'
    ImageGrab.grab(bbox=(x, y, x + target.winfo_width(), y + target.winfo_height())).save(path)
    print(path.name)


def wait(root, app, predicate):
    deadline = time.monotonic() + 8
    def check():
        if predicate() or time.monotonic() >= deadline:
            root.quit()
        else:
            root.after(10, check)
    root.after(10, check)
    root.mainloop()
    if not predicate():
        raise RuntimeError(app.online_connection_label.cget('text'))


def refresh(root, app):
    wait(root, app, lambda: not app.online_busy)
    app.online_submit('state', {})
    wait(root, app, lambda: not app.online_busy)


def main():
    scenes = ('dashboard', 'online-setup', 'lobby', 'online-game', 'connection-pause', 'round-finished', 'rematch', 'online-light')
    if len(sys.argv) == 1:
        for scene in scenes:
            subprocess.run([sys.executable, __file__, scene], check=True)
        return
    for scene in sys.argv[1:]:
        if scene not in scenes:
            raise ValueError('Unknown capture scene')
        offset = [0]
        rooms = Rooms(clock=lambda: time.monotonic() + offset[0], game_factory=lambda: GameSession(dice=seeded_dice(42)))
        server = RelayServer(('127.0.0.1', 0), rooms)
        thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .03}, daemon=True)
        thread.start()
        root = tk.Tk()
        errors = []
        root.report_callback_exception = lambda kind, error, trace: errors.append(error)
        app = HogApp(root, preferences=Preferences(animations=False))
        root.geometry('1280x880+20+20');root.update()
        try:
            if scene != 'dashboard':
                app.show_online()
            if scene not in ('dashboard', 'online-setup'):
                endpoint = 'http://127.0.0.1:' + str(server.server_port)
                app.online_address_var.set(endpoint)
                app.online_name_var.set('Meazbah')
                app.online_create_button.invoke()
                wait(root, app, lambda: app.online_room_built and not app.online_busy)
                peer = OnlineClient(endpoint)
                peer.join('Alex', app.online_state['room'])
                refresh(root, app)
                if scene != 'lobby':
                    app.online_ready_button.invoke()
                    wait(root, app, lambda: not app.online_busy)
                    peer.call('ready', {'ready': True})
                    refresh(root, app)
                    if scene in ('round-finished', 'rematch'):
                        while app.online_state['phase'] == 'playing':
                            state = app.online_state
                            if state['current_player'] == 0:
                                app.online_count_buttons[0].invoke();app.online_move_button.invoke()
                                wait(root, app, lambda: not app.online_busy)
                            else:
                                peer.call('move', peer.move_payload(state, 0));refresh(root, app)
                    else:
                        for count in (6, 5, 0, 8, 2, 5):
                            state = app.online_state
                            if state['current_player'] == 0:
                                app.online_count_buttons[count].invoke();app.online_move_button.invoke()
                                wait(root, app, lambda: not app.online_busy)
                            else:
                                peer.call('move', peer.move_payload(state, count));refresh(root, app)
                    if scene == 'connection-pause':
                        offset[0] = 10
                        refresh(root, app)
                    elif scene == 'rematch':
                        app.online_rematch_button.invoke();wait(root, app, lambda: not app.online_busy)
                        peer.call('rematch', {'ready': True});refresh(root, app)
                    elif scene == 'online-light':
                        app.set_theme('light')
            capture(root, scene, app.analysis_window)
            if errors:
                raise errors[0]
        finally:
            app.close()
            server.shutdown();server.server_close();thread.join(timeout=2)


if __name__ == '__main__':
    main()
