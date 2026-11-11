# Private Multiplayer Setup — v3.5.0

The ZIP includes a native desktop client, Python client source, and a separate Python relay. No public relay is deployed or bundled as an always-running service. Both players must reach the same running relay. The client and relay use the Python standard library; the client additionally needs Tkinter.

## Try Two Players on One Computer

In one terminal, start the relay from the extracted project folder:

```bash
python hog_server.py
```

Leave that terminal open. In two other terminals, start two desktop clients:

```bash
python hog_desktop.py
```

In each client, open **Online** in dashboard navigation. Use `http://127.0.0.1:8765`, with a different display name for each player. The first player clicks **Create private room**, chooses the timer, and copies the eight-character code. The second enters that code and clicks **Join room**. Both press **Ready**.

The included Linux executable can also join rooms. The relay itself runs from `hog_server.py` and requires Python; the client executable is not a relay executable.

An automated two-client check starts and closes its own loopback relay:

```bash
python tools/network_smoke.py
```

## Play Across a Trusted Local Network

On the host computer:

```bash
python hog_server.py --host 0.0.0.0 --port 8765
```

Use the host computer's actual LAN address in both clients, for example `http://192.168.1.50:8765`. `0.0.0.0` is a listen address, not the address to enter in the client. `127.0.0.1` always means the computer running that client, so it cannot identify another computer on the network.

The host's firewall must allow the selected TCP port on the intended network. The address and room code are both needed. Copy code copies only the room code, never the private seat token. Display names are temporary names, not authenticated local profile identities.

## Play Across the Internet with HTTPS

Run the relay on a machine reachable by both players, using a hostname and a certificate valid for that hostname. Home routers may require port forwarding; networks using carrier-grade NAT may need a separately reachable host. The game does not configure routers, create tunnels, or provision hosting.

The relay supports direct TLS:

```bash
python hog_server.py --host 0.0.0.0 --port 8765 --certfile fullchain.pem --keyfile privatekey.pem
```

Both clients enter the matching address, for example `https://hog.example.com:8765`. Use your actual hostname, port and certificate files. The server requires both certificate and key arguments together. Keep the private key on the host; it is not a client setting and must not be uploaded with the project.

The client uses normal certificate and hostname validation. For a private test certificate or private certificate authority, select the corresponding **public CA/certificate PEM file** using the optional trusted CA field. It must still validate the server's actual hostname/IP. The client provides no “disable certificate verification” option. HTTP is intended for trusted local testing; internet play should use HTTPS.

## Room Lifecycle

| Action or event | Result |
| --- | --- |
| Create | Creates a two-seat private room; the creator occupies seat 0. |
| Join | Claims an empty seat using the room code. A playing/full room rejects new joins. |
| Ready | Starts round 1 only when both occupied seats are ready and connected. |
| Human move | Sends only the dice count and current match/turn identity. The relay rolls and scores it. |
| Turn timeout | Automatically plays zero dice for the active connected player. All scoring rules still apply. |
| Disconnect | Keeps the seat token in this app's memory and stops polling. The seat is temporarily reserved. |
| Reopen Online | Reconnects with the existing token, if the seat still exists. |
| Network failure | Automatically retries, including the same identity for an interrupted move request. |
| Leave room | Removes the seat immediately; leaving an active match forfeits that round. |
| Reconnect grace expires | Removes the stale seat; an active round ends by forfeit to the remaining player, or without a winner if both expire. |
| Both request rematch | Starts a fresh round with zero scores and new server dice. The opening seat alternates each round. |
| Stop/restart relay | Removes every in-memory room, token, event log and result. |

A heartbeat becomes disconnected after **8 seconds** without a successful authenticated request. The turn timer pauses when the relay detects that absence, holding its remaining time. Both players must reconnect to resume it. The reservation expires **90 seconds after the last successful heartbeat**; it is not a fresh 90-second allowance after the disconnection label appears.

**Disconnect** and closing the multiplayer window preserve the credential only while that app process remains open. Opening another analysis view also stops multiplayer polling. App exit loses the in-memory token, so restarting the app cannot resume its old seat. A relay restart also prevents reconnection. There is no online save file, account, password reset, or durable match recovery.

## Timer and Rematch Details

The creator selects **0, 30, 60 or 120 seconds**. Zero disables the move timer. A new turn gets the selected duration. A timeout takes the real zero-dice action; it is marked in the turn journal. Timers are controlled by the relay, not the player's displayed clock.

Round 1 starts with seat 0, round 2 with seat 1, then alternates. A rematch requires both players' votes; either can cancel a vote before the next round begins. If someone leaves a finished room, another person can claim the empty seat and agree to a rematch. The result text retains the previous round's player names until the new round starts.

## Data and Protocol

Online scores, events and results stay in relay memory. They do not enter local SQLite history, standard statistics, local profile rankings, coaching/replay selectors, campaign rewards or the manual save slot. Local profile data and cosmetics are not sent to the relay. Online seats use display names and neutral dice styling.

The protocol is JSON over HTTP(S), with desktop polling approximately every 600 ms. There are no WebSocket or external Python runtime dependencies. The relay serializes room changes under a lock and sends independent state snapshots. It alone owns scoring randomness, validates seat/turn/match identity, and deduplicates retried moves. Room codes identify rooms; a separate random bearer token authenticates each seat. Tokens are sent in POST bodies, stay out of the clipboard and default logs, and are never saved to disk by the client.

Defaults are 100 rooms, 32 active request handlers, an 8 KiB request-body limit, and 100 POST requests per 10 seconds per source IP. Room activity expires after 30 idle minutes; stale seats generally expire sooner under the 90-second grace rule. These bounds support small private matches; this release does not claim a public matchmaking platform, adversarial anti-cheat certification, or large-scale deployment testing.

The app's close path disposes of cyclic view callbacks on the Tk thread, so background worker garbage collection cannot become the final owner of a destroyed view's Tcl interpreter.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Connection refused | Start the relay; confirm the address and port. A client does not start a server automatically. |
| Works locally but not on another computer | Bind the relay to its LAN interface or `0.0.0.0`; use the host's LAN address and check its firewall. |
| HTTPS verification error | Confirm the hostname, certificate validity/chain, and trusted CA file. Do not substitute a mismatched IP. |
| Room full or already playing | Use the correct code, or wait for a vacant/expired seat. |
| Seat expired/token invalid | Join a new room. An expired seat cannot be recovered using the old token. |
| Move rejected as stale/out of turn | Let the client refresh; the relay may already have accepted a prior move or applied a timeout. |
| Internet host unreachable | Check routing, public reachability, firewall and TLS setup outside the game. |

Validated here: loopback HTTP, locally trusted HTTPS, two independent clients, a completed round/rematch, simulated heartbeat expiry, and response-loss retries. Public internet routing, NAT configurations and native Windows/macOS networking were not exercised.
