"""Authoritative room rules, real HTTP/TLS clients and Tk connection lifecycle."""

from copy import deepcopy
import json
import gc
import weakref
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil
import ssl
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib import request, error
from uuid import uuid4

from hog import GameSession, seeded_dice
from hog_online import Rooms, RoomError, PROTOCOL
from hog_online_client import OnlineClient, NetworkError, endpoint_url, valid_state
from hog_server import RelayServer
from hog_desktop import HogApp, tk
from hog_preferences import Preferences


class Clock:
    def __init__(self): self.now = 0
    def __call__(self): return self.now


class RoomTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.rooms = Rooms(clock=self.clock, game_factory=lambda: GameSession(dice=seeded_dice(42)),
                           disconnect_after=8, reconnect_grace=90)
        a = self.call('create', name='Alice', turn_seconds=30, request_id=uuid4().hex)
        self.code = a['state']['room']
        b = self.call('join', name='Bob', room=self.code, request_id=uuid4().hex)
        self.tokens = [a['token'], b['token']]

    def call(self, op, **data):
        return self.rooms.request(op, {'protocol': PROTOCOL, **data})

    def player(self, seat, op='state', **data):
        return self.call(op, room=self.code, token=self.tokens[seat], **data)['state']

    def begin(self):
        self.player(0, 'ready', ready=True)
        return self.player(1, 'ready', ready=True)

    def move(self, seat, state, count=5, identity=None):
        return self.player(seat, 'move', match_id=state['match_id'], turn=state['turn'], dice=count,
                           request_id=identity or uuid4().hex)

    def test_both_ready_required_and_secrets_not_in_state(self):
        self.assertEqual(self.player(0)['phase'], 'lobby')
        self.assertEqual(self.player(0, 'ready', ready=True)['phase'], 'lobby')
        state = self.player(1, 'ready', ready=True)
        self.assertEqual((state['phase'], state['current_player']), ('playing', 0))
        encoded = json.dumps(state)
        self.assertTrue(all(token not in encoded for token in self.tokens))

    def test_out_of_turn_and_bad_dice_never_advance(self):
        state = self.begin()
        with self.assertRaises(RoomError): self.move(1, state)
        for dice in (-1, 11, True, 5.0, '5'):
            with self.assertRaises(RoomError): self.move(0, state, dice)
        self.assertEqual(self.player(0)['events'], [])

    def test_duplicate_and_stale_turn_cannot_roll_again(self):
        state = self.begin();identity = uuid4().hex
        moved = self.move(0, state, identity=identity)
        again = self.move(0, state, identity=identity)
        self.assertEqual(again['events'], moved['events'])
        with self.assertRaises(RoomError): self.move(0, state)
        self.assertEqual(len(self.player(0)['events']), 1)

    def test_server_dice_equal_authoritative_engine(self):
        state = self.begin()
        expected = GameSession(dice=seeded_dice(42))
        for count in (5, 0, 3, 8):
            event = expected.advance(count)
            state = self.move(event.player, state, count)
            self.assertEqual(tuple(state['scores']), expected.scores)
            self.assertEqual(tuple(state['events'][-1]['event']['outcomes']), event.outcomes)

    def test_expired_turn_automatically_takes_zero_dice(self):
        self.begin()
        for now in (7, 14, 21, 28):
            self.clock.now = now;self.player(0);self.player(1)
        self.clock.now = 31
        state = self.player(0)
        self.assertEqual(len(state['events']), 1)
        self.assertTrue(state['events'][0]['automatic'])
        self.assertEqual(state['events'][0]['event']['num_rolls'], 0)

    def test_disconnect_pauses_and_reconnect_restores_remaining_timer(self):
        self.begin()
        self.clock.now = 9
        paused = self.player(0)
        self.assertTrue(paused['paused'])
        remaining = paused['turn_remaining']
        self.clock.now = 15
        resumed = self.player(1)
        self.assertFalse(resumed['paused'])
        self.assertEqual(resumed['turn_remaining'], remaining)
        self.assertEqual(resumed['events'], [])

    def test_grace_expiry_forfeits_and_invalidates_old_token(self):
        self.begin()
        for now in range(7, 92, 7):
            self.clock.now = now;self.player(0)
        self.clock.now = 92
        state = self.player(0)
        self.assertEqual(state['result'], {'winner': 0, 'reason': 'reconnect-expired'})
        with self.assertRaises(RoomError): self.player(1)

    def test_rematch_requires_both_and_alternates_starter(self):
        state = self.begin()
        while state['phase'] == 'playing':
            state = self.move(state['current_player'], state, 0)
        old_id = state['match_id']
        self.assertEqual(self.player(0, 'rematch', ready=True)['phase'], 'finished')
        new = self.player(1, 'rematch', ready=True)
        self.assertEqual((new['round'], new['current_player']), (2, 1))
        self.assertEqual(new['scores'], (0, 0))
        self.assertNotEqual(old_id, new['match_id'])

    def test_leave_finishes_match_and_allows_new_guest(self):
        self.begin()
        self.call('leave', room=self.code, token=self.tokens[1])
        state = self.player(0)
        self.assertEqual(state['result']['reason'], 'left-room')
        new = self.call('join', name='Carol', room=self.code, request_id=uuid4().hex)
        self.assertEqual(new['state']['you'], 1)
        self.assertEqual(new['state']['match_names'], ('Alice', 'Bob'))

    def test_full_room_and_unauthorized_poll_rejected(self):
        with self.assertRaises(RoomError): self.call('join', room=self.code, name='Third', request_id=uuid4().hex)
        with self.assertRaises(RoomError): self.call('state', room=self.code, token='wrong')

    def test_handshake_retries_return_the_same_seat(self):
        identity = uuid4().hex
        first = self.call('create', name='Other', turn_seconds=60, request_id=identity)
        again = self.call('create', name='Other', turn_seconds=60, request_id=identity)
        self.assertEqual(first['token'], again['token'])
        with self.assertRaises(RoomError): self.call('create', name='Changed', turn_seconds=60, request_id=identity)

    def test_old_round_move_is_rejected_after_rematch(self):
        old = self.begin()
        current = old
        while current['phase'] == 'playing':
            current = self.move(current['current_player'], current, 0)
        self.player(0, 'rematch', ready=True)
        self.player(1, 'rematch', ready=True)
        with self.assertRaises(RoomError): self.move(1, old)
        self.assertEqual(self.player(0)['events'], [])

    def test_disabled_timer_does_not_create_automatic_turns(self):
        room = self.rooms.rooms[self.code]
        room.timer = 0
        self.begin()
        for now in range(7, 100, 7):
            self.clock.now = now;self.player(0);self.player(1)
        self.assertEqual(self.player(0)['events'], [])

    def test_ready_lobby_starts_when_a_waiting_player_reconnects(self):
        self.player(0, 'ready', ready=True)
        self.clock.now = 9
        self.assertEqual(self.player(1, 'ready', ready=True)['phase'], 'lobby')
        self.assertEqual(self.player(0)['phase'], 'playing')

    def test_state_is_a_snapshot_not_a_live_list(self):
        state = self.begin()
        snapshot = deepcopy(state)
        self.move(0, state)
        self.assertEqual(state, snapshot)

    def test_protocol_names_and_timer_validation(self):
        with self.assertRaises(RoomError): self.rooms.request('create', {'protocol': True})
        for name in ('', 'x' * 21, 'bad\nname'):
            with self.assertRaises(RoomError): self.call('create', name=name, request_id=uuid4().hex)
        with self.assertRaises(RoomError): self.call('create', name='A', turn_seconds=True, request_id=uuid4().hex)

    def test_empty_rooms_are_removed_and_capacity_is_bounded(self):
        rooms = Rooms(clock=self.clock, max_rooms=1)
        rooms.request('create', {'protocol': 1, 'name': 'A', 'request_id': uuid4().hex})
        with self.assertRaises(RoomError): rooms.request('create', {'protocol': 1, 'name': 'B', 'request_id': uuid4().hex})
        self.clock.now = 100
        rooms.tick()
        self.assertEqual(rooms.rooms, {})


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.server = RelayServer(('127.0.0.1', 0))
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': .03}, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)

    def test_two_real_clients_complete_game_and_rematch(self):
        a, b = OnlineClient(self.url), OnlineClient(self.url)
        created = a.create('Alice', 0)['state']
        b.join('Bob', created['room'])
        a.call('ready', {'ready': True})
        state = b.call('ready', {'ready': True})['state']
        clients = (a, b)
        while state['phase'] == 'playing':
            client = clients[state['current_player']]
            state = client.call('move', client.move_payload(state, 0))['state']
        self.assertEqual(len(state['events']), state['turn'] - 1)
        self.assertGreaterEqual(max(state['scores']), 100)
        a.call('rematch', {'ready': True})
        state = b.call('rematch', {'ready': True})['state']
        self.assertEqual((state['round'], state['current_player']), (2, 1))

    def test_health_and_malformed_body(self):
        with request.urlopen(self.url + '/health') as response:
            self.assertEqual(json.load(response)['protocol'], 1)
        req = request.Request(self.url + '/api/create', data=b'{broken', headers={'Content-Type': 'application/json'})
        with self.assertRaises(error.HTTPError) as caught: request.urlopen(req)
        self.assertEqual(caught.exception.code, 400)

    def test_client_reconnects_with_its_existing_token(self):
        a = OnlineClient(self.url);a.create('Alice')
        token = a.token
        state = a.call('state')['state']
        self.assertEqual(a.token, token)
        self.assertEqual(state['you'], 0)

    def test_tls_requires_trusted_certificate(self):
        if shutil.which('openssl') is None: self.skipTest('OpenSSL needed for temporary TLS certificate')
        self.server.shutdown();self.thread.join(timeout=2)
        with tempfile.TemporaryDirectory() as folder:
            cert, key = Path(folder)/'cert.pem', Path(folder)/'key.pem'
            subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                            '-keyout', str(key), '-out', str(cert), '-subj', '/CN=localhost',
                            '-addext', 'subjectAltName=IP:127.0.0.1,DNS:localhost'], check=True, capture_output=True)
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(cert, key)
            self.server.socket = context.wrap_socket(self.server.socket, server_side=True)
            self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': .03}, daemon=True)
            self.thread.start()
            url = 'https://127.0.0.1:' + str(self.server.server_port)
            with self.assertRaises(NetworkError): OnlineClient(url).create('Untrusted')
            trusted = OnlineClient(url, cafile=str(cert))
            self.assertEqual(trusted.create('Trusted')['state']['phase'], 'lobby')

    def test_request_limits_and_invalid_display_state(self):
        req = request.Request(self.url + '/api/create', data=b'x' * 8200, headers={'Content-Type': 'application/json'})
        with self.assertRaises(error.HTTPError) as caught: request.urlopen(req)
        self.assertEqual(caught.exception.code, 413)
        for _ in range(99): self.server.allowed('example-ip')
        self.assertTrue(self.server.allowed('example-ip'))
        self.assertFalse(self.server.allowed('example-ip'))
        state = OnlineClient(self.url).create('Alice')['state']
        broken = deepcopy(state);broken['scores'] = [1]
        self.assertFalse(valid_state(broken))
        broken = deepcopy(state);broken['players'][0]['name'] = 'bad\nname'
        self.assertFalse(valid_state(broken))

    def test_client_rejects_unsupported_endpoints(self):
        for url in ('file:///tmp/game', 'https://user:pass@example.org', 'http://localhost/?token=abc', 'http://localhost/path'):
            with self.assertRaises(ValueError): endpoint_url(url)


class OnlineDesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if tk is None: raise unittest.SkipTest('Tk not installed')
        try:
            root = tk.Tk();root.destroy()
        except tk.TclError: raise unittest.SkipTest('Graphical display required')

    def setUp(self):
        self.server = RelayServer(('127.0.0.1', 0))
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': .03}, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)
        self.root = tk.Tk();self.errors = []
        self.root.report_callback_exception = lambda kind, value, trace: self.errors.append(value)
        self.app = HogApp(self.root, preferences=Preferences(animations=False))
        self.root.update()
        self.peer = OnlineClient(self.url)

    def tearDown(self):
        self.app.close()
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)
        self.assertEqual(self.errors, [])

    def wait_for(self, predicate):
        end = time.monotonic() + 5
        def poll():
            if predicate() or time.monotonic() > end:
                self.root.quit()
            else: self.root.after(15, poll)
        self.root.after(15, poll);self.root.mainloop()
        self.assertTrue(predicate(), self.app.online_connection_label.cget('text'))

    def connect(self):
        self.app.show_online()
        self.app.online_address_var.set(self.url)
        self.app.online_name_var.set('Alice')
        self.app.online_create_button.invoke()
        self.wait_for(lambda: self.app.online_room_built and not self.app.online_busy)

    def begin(self):
        self.connect()
        self.peer.join('Bob', self.app.online_state['room'])
        self.app.online_ready_button.invoke()
        self.wait_for(lambda: not self.app.online_busy)
        self.peer.call('ready', {'ready': True})
        self.wait_for(lambda: self.app.online_state['phase'] == 'playing' and not self.app.online_busy)

    def test_two_clients_render_and_send_a_real_turn(self):
        self.begin()
        self.app.online_count_buttons[0].invoke()
        self.app.online_move_button.invoke()
        self.wait_for(lambda: len(self.app.online_state['events']) == 1 and not self.app.online_busy)
        peer = self.peer.call('state')['state']
        self.assertEqual(peer['scores'], self.app.online_state['scores'])
        self.assertEqual(self.app.store.history(), [])
        self.assertEqual(str(self.app.online_move_button.cget('state')), 'disabled')

    def test_lost_move_response_retries_same_id_without_double_roll(self):
        self.begin()
        original = self.app.online_client.call
        attempts = []
        def flaky(operation, payload=None):
            if operation == 'move':
                attempts.append(payload['request_id'])
                result = original(operation, payload)
                if len(attempts) == 1:
                    raise NetworkError('Simulated response loss')
                return result
            return original(operation, payload)
        with patch.object(self.app.online_client, 'call', side_effect=flaky):
            self.app.online_move_button.invoke()
            self.wait_for(lambda: len(attempts) >= 2 and not self.app.online_busy and len(self.app.online_state['events']) == 1)
        self.assertEqual(len(set(attempts)), 1)
        self.assertEqual(len(self.peer.call('state')['state']['events']), 1)

    def test_closed_view_cycles_are_released_before_worker_gc(self):
        other_root = tk.Tk()
        other_app = HogApp(other_root, preferences=Preferences(animations=False))
        other_app.show_puzzles()
        other_root.update()
        reference = weakref.ref(other_app)
        other_app.close()
        del other_app, other_root
        self.assertIsNone(reference())
        with ThreadPoolExecutor(max_workers=1) as executor:
            executor.submit(gc.collect).result(timeout=5)

    def test_closing_and_reopening_reuses_seat_token(self):
        self.connect()
        token = self.app.online_client.token
        self.app.close_analysis()
        self.assertIsNone(self.app.analysis_pending)
        self.app.show_online()
        self.wait_for(lambda: self.app.online_room_built and not self.app.online_busy)
        self.assertEqual(self.app.online_client.token, token)

    def test_leave_clears_credentials(self):
        self.connect()
        self.app.online_leave_button.invoke()
        self.wait_for(lambda: self.app.online_client is None)
        self.assertFalse(self.app.online_room_built)

    def test_room_controls_fit_and_theme_changes_are_read_only(self):
        self.begin()
        before = deepcopy(self.app.online_state['events'])
        self.app.analysis_window.geometry('900x720')
        for theme in ('light', 'contrast', 'dark'):
            self.app.set_theme(theme);self.root.update()
        for button in (*self.app.online_count_buttons, self.app.online_move_button, self.app.online_disconnect_button):
            self.assertTrue(button.winfo_ismapped())
            self.assertLessEqual(button.winfo_rooty()+button.winfo_height(), self.app.analysis_window.winfo_rooty()+720)
        self.assertEqual(self.app.online_state['events'], before)
