"""Verify two real HTTP clients, a completed round and a rematch on loopback."""

from pathlib import Path
import sys
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hog_server import RelayServer
from hog_online_client import OnlineClient


def main():
    server = RelayServer(('127.0.0.1', 0))
    thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .05}, daemon=True)
    thread.start()
    try:
        endpoint = 'http://127.0.0.1:' + str(server.server_port)
        first, second = OnlineClient(endpoint), OnlineClient(endpoint)
        state = first.create('Sample A', 0)['state']
        second.join('Sample B', state['room'])
        first.call('ready', {'ready': True})
        state = second.call('ready', {'ready': True})['state']
        while state['phase'] == 'playing':
            client = (first, second)[state['current_player']]
            state = client.call('move', client.move_payload(state, 0))['state']
        assert max(state['scores']) >= 100
        assert first.call('state')['state']['scores'] == second.call('state')['state']['scores']
        first.call('rematch', {'ready': True})
        state = second.call('rematch', {'ready': True})['state']
        assert state['round'] == 2 and state['current_player'] == 1
        print('PASS: two clients synchronized, completed a round, and started an alternating-seat rematch.')
    finally:
        server.shutdown();server.server_close();thread.join(timeout=2)


if __name__ == '__main__':
    main()
