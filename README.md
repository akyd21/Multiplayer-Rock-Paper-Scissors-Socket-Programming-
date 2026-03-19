# Multiplayer Rock-Paper-Scissors (Socket Programming)

This project is a simple multiplayer Rock-Paper-Scissors game built with:

- Python TCP sockets for game communication
- Multithreading on the server for handling multiple clients
- A web UI (HTML/CSS/JavaScript) served through Flask

## Project Structure

```text
rps-multiplayer/
├── server.py
├── client.py
├── templates/
│   └── index.html
├── static/
│   ├── style.css
│   └── script.js
└── README.md
```

## Features

- 2-player support
- Player roles (Player 1 / Player 2)
- Input validation (server + client)
- Winner detection (Win / Lose / Draw)
- Multiple rounds
- Server logs for connections, moves, and results

## Requirements

- Python 3.9+
- Flask

Install Flask:

```bash
pip install flask
```

## Step-by-Step: How to Run

Open 3 terminals and run these commands.

### 1) Start the game server

```bash
cd rps-multiplayer
python server.py
```

The server listens on `0.0.0.0:5555`.

### 2) Start web client instance for Player 1

```bash
cd rps-multiplayer
python client.py --server-host 127.0.0.1 --server-port 5555 --web-port 5000
```

Open browser: `http://127.0.0.1:5000`

### 3) Start web client instance for Player 2

In another terminal:

```bash
cd rps-multiplayer
python client.py --server-host 127.0.0.1 --server-port 5555 --web-port 5001
```

Open browser: `http://127.0.0.1:5001`

Now click **Join Game** in both browser windows, then play rounds.

## How Socket Communication Works in This Project

1. `server.py` creates a TCP socket (`AF_INET`, `SOCK_STREAM`) and listens for client connections.
2. Each `client.py` connects to the server using a TCP socket.
3. The server assigns connected users as Player 1 or Player 2.
4. A player move is sent as a text message:
   - `MOVE rock`
   - `MOVE paper`
   - `MOVE scissors`
5. Server waits until both players send valid moves.
6. Server calculates winner and sends each player a personalized `RESULT` message.
7. Server resets round data and accepts next round moves.

### Message Examples

- `WELCOME Player 1`
- `START Both players connected...`
- `ACK Choice received: rock`
- `RESULT Round 1 | You: rock | Opponent: scissors | Outcome: Win`
- `NEXT Next round started. Send your move.`

## Notes

- The browser cannot directly open raw TCP sockets, so `client.py` works as a bridge:
  - Browser <-> Flask HTTP API (`/api/*`)
  - Flask client <-> Game server via TCP sockets
- If one player disconnects, server keeps running and waits for another player.
