"""Authoritative, in-memory private-room rules. No sockets, UI or local DB writes."""

from dataclasses import dataclass, field, asdict
import secrets
from copy import deepcopy
import threading
import time
from uuid import uuid4

from hog import GameSession, seeded_dice

PROTOCOL = 1
ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'


class RoomError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def nickname(value):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 20 or not all(c.isprintable() for c in value):
        raise RoomError('Use a display name of 1-20 printable characters.')
    return value.strip()


def request_identity(value):
    if not isinstance(value, str) or len(value) != 32 or any(c not in '0123456789abcdef' for c in value):
        raise RoomError('Invalid request identity.')
    return value


@dataclass
class Player:
    name: str
    token: str
    last_seen: float
    ready: bool = False
    rematch: bool = False


@dataclass
class Room:
    code: str
    timer: int
    players: list
    created: float
    touched: float
    phase: str = 'lobby'
    game: object = None
    events: list = field(default_factory=list)
    round_number: int = 0
    match_id: str = ''
    match_names: tuple = ()
    result: dict | None = None
    deadline: float | None = None
    remaining: float | None = None
    paused: bool = False
    revision: int = 0
    processed: list = field(default_factory=list)


class Rooms:
    def __init__(self, *, clock=time.monotonic, game_factory=None, disconnect_after=8, reconnect_grace=90,
                 room_ttl=1800, max_rooms=100):
        self.clock = clock
        self.game_factory = game_factory or (lambda: GameSession(dice=seeded_dice(secrets.randbits(128))))
        self.disconnect_after = disconnect_after
        self.reconnect_grace = reconnect_grace
        self.room_ttl = room_ttl
        self.max_rooms = max_rooms
        self.rooms = {}
        self.handshakes = {}
        self.lock = threading.RLock()

    def _new_player(self, name, now):
        return Player(nickname(name), secrets.token_urlsafe(32), now)

    def _start(self, room, now):
        if any(player is None for player in room.players):
            raise RoomError('Two players are required.', 409)
        room.game = self.game_factory()
        room.round_number += 1
        room.game.current_player = (room.round_number - 1) % 2
        room.match_names = tuple(player.name for player in room.players)
        room.match_id = uuid4().hex
        room.events, room.processed = [], []
        room.result, room.paused = None, False
        room.phase = 'playing'
        room.deadline = now + room.timer if room.timer else None
        room.remaining = None
        for player in room.players:
            player.ready = True
            player.rematch = False
        room.revision += 1

    def _finish_without_goal(self, room, winner, reason):
        room.phase = 'finished'
        room.result = {'winner': winner, 'reason': reason}
        room.deadline, room.remaining, room.paused = None, None, False
        room.revision += 1

    def _move(self, room, count, now, *, automatic=False):
        event = room.game.advance(count)
        room.events.append({'event': asdict(event), 'automatic': automatic})
        room.revision += 1
        if room.game.finished:
            room.phase = 'finished'
            room.result = {'winner': room.game.winner, 'reason': 'goal'}
            room.deadline = None
        else:
            room.deadline = now + room.timer if room.timer else None

    def _tick_room(self, room, now):
        expired = [seat for seat, player in enumerate(room.players)
                   if player and now - player.last_seen > self.reconnect_grace]
        if expired and room.phase == 'playing':
            other = 1 - expired[0]
            winner = other if len(expired) == 1 and room.players[other] is not None else None
            self._finish_without_goal(room, winner, 'reconnect-expired')
        for seat in expired:
            room.players[seat] = None
            room.revision += 1
        if room.phase != 'playing':
            return
        online = all(player and now - player.last_seen <= self.disconnect_after for player in room.players)
        if not online and not room.paused:
            room.remaining = max(0, room.deadline - now) if room.deadline is not None else None
            room.deadline = None
            room.paused = True
            room.revision += 1
        elif online and room.paused:
            room.deadline = now + room.remaining if room.remaining is not None else None
            room.remaining = None
            room.paused = False
            room.revision += 1
        if online and room.deadline is not None and now >= room.deadline:
            self._move(room, 0, now, automatic=True)

    def tick(self):
        with self.lock:
            now = self.clock()
            for code, room in list(self.rooms.items()):
                self._tick_room(room, now)
                if now - room.touched > self.room_ttl or not any(room.players):
                    self.rooms.pop(code, None)
            self.handshakes = {key: value for key, value in self.handshakes.items() if now - value[0] < 120}

    def _room(self, code):
        if not isinstance(code, str):
            raise RoomError('Enter an eight-character room code.')
        room = self.rooms.get(code.strip().upper())
        if room is None:
            raise RoomError('Room not found or expired. Create or join a new room.', 404)
        return room

    def _auth(self, room, token, now):
        if not isinstance(token, str):
            raise RoomError('A seat token is required.', 401)
        for seat, player in enumerate(room.players):
            if player and secrets.compare_digest(player.token, token):
                player.last_seen = now
                room.touched = now
                self._tick_room(room, now)
                return seat
        raise RoomError('Seat expired or token invalid. Join a new room.', 401)

    def _state(self, room, seat, now):
        remaining = room.remaining if room.paused else max(0, room.deadline - now) if room.deadline is not None else None
        players = [None if player is None else {'name': player.name, 'ready': player.ready,
                    'rematch': player.rematch, 'connected': now - player.last_seen <= self.disconnect_after,
                    'reconnect_remaining': max(0, self.reconnect_grace - (now - player.last_seen))}
                   for player in room.players]
        return {'protocol': PROTOCOL, 'room': room.code, 'you': seat, 'players': players,
                'phase': room.phase, 'round': room.round_number, 'match_id': room.match_id,
                'match_names': room.match_names, 'scores': room.game.scores if room.game else (0, 0),
                'turn': room.game.turn_number if room.game else 0,
                'current_player': room.game.current_player if room.game else 0,
                'events': deepcopy(room.events), 'result': deepcopy(room.result), 'turn_seconds': room.timer,
                'turn_remaining': remaining, 'paused': room.paused, 'revision': room.revision}

    def request(self, operation, payload):
        if not isinstance(payload, dict) or payload.get('protocol') != PROTOCOL or type(payload.get('protocol')) is not int:
            raise RoomError('Unsupported protocol. Use a compatible v3.5.0 client.')
        with self.lock:
            self.tick()
            now = self.clock()
            if operation in ('create', 'join'):
                identity = request_identity(payload.get('request_id'))
                name = nickname(payload.get('name'))
                fingerprint = (operation, name, payload.get('room'), payload.get('turn_seconds'))
                if identity in self.handshakes:
                    _, old_fingerprint, code, token = self.handshakes[identity]
                    if fingerprint != old_fingerprint:
                        raise RoomError('Request identity reused with different data.', 409)
                    room = self._room(code)
                    seat = self._auth(room, token, now)
                    return {'token': token, 'state': self._state(room, seat, now)}
                if operation == 'create':
                    timer = payload.get('turn_seconds', 60)
                    if type(timer) is not int or timer not in (0, 30, 60, 120):
                        raise RoomError('Choose a disabled, 30, 60 or 120-second timer.')
                    if len(self.rooms) >= self.max_rooms:
                        raise RoomError('Server room limit reached. Try again later.', 503)
                    code = ''.join(secrets.choice(ALPHABET) for _ in range(8))
                    while code in self.rooms:
                        code = ''.join(secrets.choice(ALPHABET) for _ in range(8))
                    room = Room(code, timer, [self._new_player(name, now), None], now, now)
                    self.rooms[code] = room
                    seat = 0
                else:
                    room = self._room(payload.get('room'))
                    if room.phase == 'playing':
                        raise RoomError('This room already has a match in progress.', 409)
                    try:
                        seat = room.players.index(None)
                    except ValueError as error:
                        raise RoomError('This room is full.', 409) from error
                    room.players[seat] = self._new_player(name, now)
                    room.touched = now
                    room.revision += 1
                token = room.players[seat].token
                self.handshakes[identity] = (now, fingerprint, room.code, token)
                if len(self.handshakes) > self.max_rooms * 4:
                    oldest = next(iter(self.handshakes))
                    self.handshakes.pop(oldest)
                return {'token': token, 'state': self._state(room, seat, now)}
            room = self._room(payload.get('room'))
            seat = self._auth(room, payload.get('token'), now)
            player = room.players[seat]
            if operation == 'state':
                if room.phase in ('lobby', 'finished') and all(p and now - p.last_seen <= self.disconnect_after for p in room.players):
                    flags = [p.ready if room.phase == 'lobby' else p.rematch for p in room.players]
                    if all(flags):
                        self._start(room, now)
                return {'state': self._state(room, seat, now)}
            if operation == 'ready':
                if room.phase != 'lobby' or type(payload.get('ready')) is not bool:
                    raise RoomError('Ready status is available only in the lobby.', 409)
                player.ready = payload['ready']
                room.revision += 1
                if all(p and p.ready and now - p.last_seen <= self.disconnect_after for p in room.players):
                    self._start(room, now)
            elif operation == 'move':
                identity = request_identity(payload.get('request_id'))
                key = (player.token, payload.get('match_id'), identity)
                if key in room.processed:
                    return {'state': self._state(room, seat, now)}
                count = payload.get('dice')
                if type(count) is not int or not 0 <= count <= 10:
                    raise RoomError('Dice count must be an integer from 0 to 10.')
                if room.phase != 'playing' or room.paused:
                    raise RoomError('The match is not accepting moves right now.', 409)
                if payload.get('match_id') != room.match_id or type(payload.get('turn')) is not int or payload['turn'] != room.game.turn_number:
                    raise RoomError('The position changed. Refresh before choosing a move.', 409)
                if seat != room.game.current_player:
                    raise RoomError('Wait for your turn.', 409)
                self._move(room, count, now)
                room.processed.append(key)
                room.processed = room.processed[-256:]
            elif operation == 'rematch':
                if room.phase != 'finished' or type(payload.get('ready')) is not bool:
                    raise RoomError('Rematch voting is available after a match finishes.', 409)
                player.rematch = payload['ready']
                room.revision += 1
                if all(p and p.rematch and now - p.last_seen <= self.disconnect_after for p in room.players):
                    self._start(room, now)
            elif operation == 'leave':
                if room.phase == 'playing':
                    self._finish_without_goal(room, 1 - seat, 'left-room')
                room.players[seat] = None
                room.revision += 1
                return {'left': True}
            else:
                raise RoomError('Unknown room operation.', 404)
            return {'state': self._state(room, seat, now)}
