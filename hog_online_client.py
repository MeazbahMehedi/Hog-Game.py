"""Small JSON relay client. Credentials stay in this process, never on disk."""

import json
import math
import ssl
from urllib import request, error, parse
from uuid import uuid4

from hog_online import PROTOCOL, ALPHABET


class NetworkError(Exception):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


def endpoint_url(value):
    if not isinstance(value, str):
        raise ValueError('Enter a server URL.')
    value = value.strip().rstrip('/')
    parsed = parse.urlsplit(value)
    if (parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path not in ('', '/') or parsed.port == 0):
        raise ValueError('Use http(s)://host:port with no credentials, query or path.')
    return value


def valid_state(state):
    """Bound untrusted display data before it reaches Tk callbacks."""
    try:
        if (type(state['protocol']) is not int or state['protocol'] != PROTOCOL
                or type(state['you']) is not int or state['you'] not in (0, 1)
                or state['phase'] not in ('lobby', 'playing', 'finished')
                or not isinstance(state['room'], str) or len(state['room']) != 8
                or any(c not in ALPHABET for c in state['room'])):
            return False
        if (not isinstance(state['players'], list) or len(state['players']) != 2
                or not isinstance(state['scores'], list) or len(state['scores']) != 2
                or any(type(score) is not int or not 0 <= score <= 200 for score in state['scores'])
                or type(state['turn']) is not int or not 0 <= state['turn'] <= 201
                or type(state['round']) is not int or state['round'] < 0
                or type(state['current_player']) is not int or state['current_player'] not in (0, 1)
                or type(state['paused']) is not bool or type(state['turn_seconds']) is not int
                or state['turn_seconds'] not in (0, 30, 60, 120)):
            return False
        def name_ok(name):
            return isinstance(name, str) and 1 <= len(name) <= 20 and all(c.isprintable() for c in name)
        for player in state['players']:
            if player is not None and (not name_ok(player['name']) or any(type(player[key]) is not bool for key in ('ready', 'rematch', 'connected'))
                    or not isinstance(player['reconnect_remaining'], (int, float)) or not math.isfinite(player['reconnect_remaining'])):
                return False
        if state['players'][state['you']] is None:
            return False
        if not isinstance(state['match_names'], list) or len(state['match_names']) not in (0, 2) or any(not name_ok(name) for name in state['match_names']):
            return False
        if not isinstance(state['match_id'], str) or len(state['match_id']) not in (0, 32):
            return False
        if state['turn_remaining'] is not None and (type(state['turn_remaining']) not in (int, float) or not math.isfinite(state['turn_remaining']) or not 0 <= state['turn_remaining'] <= 120):
            return False
        if not isinstance(state['events'], list) or len(state['events']) > 200:
            return False
        for wrapped in state['events']:
            event = wrapped['event']
            if (type(wrapped['automatic']) is not bool or type(event['player']) is not int or event['player'] not in (0, 1)
                    or type(event['num_rolls']) is not int or not 0 <= event['num_rolls'] <= 10
                    or not isinstance(event['outcomes'], list) or len(event['outcomes']) != event['num_rolls']
                    or any(type(face) is not int or not 1 <= face <= 6 for face in event['outcomes'])
                    or any(type(event[key]) is not int or not 0 <= event[key] <= 200 for key in
                           ('number', 'score_before', 'opponent_score', 'turn_points', 'score_after'))):
                return False
        if state['phase'] != 'lobby' and len(state['match_names']) != 2:
            return False
        result = state['result']
        if state['phase'] == 'finished' and (not isinstance(result, dict) or result['winner'] not in (None, 0, 1)
                or result['reason'] not in ('goal', 'left-room', 'reconnect-expired')):
            return False
        return True
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


class OnlineClient:
    def __init__(self, endpoint, *, cafile=None, timeout=3):
        self.endpoint = endpoint_url(endpoint)
        self.context = ssl.create_default_context(cafile=cafile or None)
        self.timeout = timeout
        self.room, self.token = None, None

    def call(self, operation, payload=None):
        data = dict(payload or {})
        data['protocol'] = PROTOCOL
        if self.room is not None:
            data.setdefault('room', self.room)
        if self.token is not None:
            data['token'] = self.token
        encoded = json.dumps(data, allow_nan=False).encode('utf-8')
        req = request.Request(self.endpoint + '/api/' + operation, data=encoded,
                              headers={'Content-Type': 'application/json', 'Accept': 'application/json'})
        try:
            with request.urlopen(req, context=self.context, timeout=self.timeout) as response:
                body = response.read(524289)
                if len(body) > 524288:
                    raise NetworkError('Server response exceeds the client limit.')
                result = json.loads(body)
        except error.HTTPError as failure:
            try:
                message = json.loads(failure.read(8192)).get('error', 'Server rejected the request.')
            except (ValueError, AttributeError):
                message = 'Server rejected the request.'
            raise NetworkError(message, failure.code) from failure
        except (error.URLError, OSError, TimeoutError, ValueError) as failure:
            raise NetworkError('Could not reach or verify the server. Check its address, certificate and connection.') from failure
        if not isinstance(result, dict) or ('state' not in result and not result.get('left')):
            raise NetworkError('The server returned an incompatible response.')
        if 'state' in result:
            state = result['state']
            if not isinstance(state, dict) or not valid_state(state):
                raise NetworkError('The server returned an incompatible room state.')
            if 'token' in result:
                if not isinstance(result['token'], str) or not 20 <= len(result['token']) <= 128:
                    raise NetworkError('The server returned an invalid seat token.')
                self.token, self.room = result['token'], state['room']
        return result

    def create(self, name, timer=60):
        return self.call('create', {'name': name, 'turn_seconds': timer, 'request_id': uuid4().hex})

    def join(self, name, room):
        return self.call('join', {'name': name, 'room': room.strip().upper(), 'request_id': uuid4().hex})

    def move_payload(self, state, count):
        return {'match_id': state['match_id'], 'turn': state['turn'], 'dice': count, 'request_id': uuid4().hex}
