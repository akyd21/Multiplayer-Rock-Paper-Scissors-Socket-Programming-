import argparse
import queue
import socket
import threading
from dataclasses import dataclass, field
from typing import Optional

from flask import Flask, jsonify, render_template, request


VALID_CHOICES = {"rock", "paper", "scissors"}


@dataclass
class ClientState:
    player_name: str = "Unknown"
    status: str = "Disconnected"
    last_message: str = ""
    last_result: str = ""
    last_outcome: str = ""
    connected: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)


class RPSWebClient:
    """Bridge between browser UI and TCP game server."""

    def __init__(self, server_host: str, server_port: int):
        self.server_host = server_host
        self.server_port = server_port
        self.socket: Optional[socket.socket] = None
        self.state = ClientState()
        self.send_queue: "queue.Queue[str]" = queue.Queue()
        self.stop_event = threading.Event()

    def connect(self) -> None:
        if self.socket:
            return

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((self.server_host, self.server_port))
        self.socket = sock

        with self.state.lock:
            self.state.connected = True
            self.state.status = "Connected to game server"
            self.state.last_message = "Connected. Waiting for welcome message..."

        threading.Thread(target=self._receiver_loop, daemon=True).start()
        threading.Thread(target=self._sender_loop, daemon=True).start()

    def send_move(self, move: str) -> None:
        self.send_queue.put(f"MOVE {move}")

    def _sender_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                message = self.send_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if not self.socket:
                continue

            try:
                self.socket.sendall((message + "\n").encode("utf-8"))
            except OSError:
                self._set_disconnected("Connection lost while sending.")
                return

    def _receiver_loop(self) -> None:
        if not self.socket:
            return

        buffer = ""
        while not self.stop_event.is_set():
            try:
                data = self.socket.recv(1024)
                if not data:
                    self._set_disconnected("Server closed the connection.")
                    return
            except OSError:
                self._set_disconnected("Connection lost.")
                return

            buffer += data.decode("utf-8", errors="ignore")
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                message = line.strip()
                if message:
                    self._handle_server_message(message)

    def _handle_server_message(self, message: str) -> None:
        with self.state.lock:
            self.state.last_message = message

            if message.startswith("WELCOME"):
                self.state.player_name = message.replace("WELCOME", "").strip()
                self.state.status = "Ready"
            elif message.startswith("START"):
                self.state.status = "Game started"
            elif message.startswith("WAIT"):
                self.state.status = message
            elif message.startswith("ACK"):
                self.state.status = "Move submitted"
            elif message.startswith("RESULT"):
                self.state.last_result = message
                if "Outcome:" in message:
                    self.state.last_outcome = message.split("Outcome:", 1)[1].strip()
                self.state.status = "Round completed"
            elif message.startswith("NEXT"):
                self.state.status = "Next round: choose your move"
            elif message.startswith("ERROR"):
                self.state.status = message

    def _set_disconnected(self, reason: str) -> None:
        with self.state.lock:
            self.state.connected = False
            self.state.status = "Disconnected"
            self.state.last_message = reason

        self.stop_event.set()
        try:
            if self.socket:
                self.socket.close()
        except OSError:
            pass
        self.socket = None


def create_app(server_host: str, server_port: int) -> Flask:
    app = Flask(__name__)

    session_clients: dict[str, RPSWebClient] = {}
    clients_lock = threading.Lock()

    def get_client_id() -> Optional[str]:
        client_id = request.headers.get("X-Client-Id", "").strip()
        if not client_id:
            return None
        if len(client_id) > 128:
            return None
        return client_id

    def get_session_client(create: bool = False) -> Optional[RPSWebClient]:
        client_id = get_client_id()
        if not client_id:
            return None

        with clients_lock:
            game_client = session_clients.get(client_id)
            if not game_client and create:
                game_client = RPSWebClient(server_host, server_port)
                session_clients[client_id] = game_client
            return game_client

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/join", methods=["POST"])
    def join():
        game_client = get_session_client(create=True)
        if not game_client:
            return jsonify({"ok": False, "error": "Missing or invalid client id."}), 400

        try:
            game_client.connect()
        except OSError as exc:
            return jsonify({"ok": False, "error": f"Could not connect: {exc}"}), 400

        return jsonify({"ok": True})

    @app.route("/api/play", methods=["POST"])
    def play():
        game_client = get_session_client(create=False)
        if not game_client:
            return jsonify({"ok": False, "error": "Join game first."}), 400

        payload = request.get_json(silent=True) or {}
        move = str(payload.get("move", "")).strip().lower()

        if move not in VALID_CHOICES:
            return jsonify({"ok": False, "error": "Invalid move. Use rock, paper, or scissors."}), 400

        if not game_client.state.connected:
            return jsonify({"ok": False, "error": "Not connected to game server."}), 400

        game_client.send_move(move)
        return jsonify({"ok": True, "message": f"Move sent: {move}"})

    @app.route("/api/state", methods=["GET"])
    def state():
        game_client = get_session_client(create=False)
        if not game_client:
            return jsonify(
                {
                    "player": "Unknown",
                    "status": "Not joined",
                    "last_message": "Click Join Game to connect.",
                    "last_result": "",
                    "last_outcome": "",
                    "connected": False,
                }
            )

        with game_client.state.lock:
            return jsonify(
                {
                    "player": game_client.state.player_name,
                    "status": game_client.state.status,
                    "last_message": game_client.state.last_message,
                    "last_result": game_client.state.last_result,
                    "last_outcome": game_client.state.last_outcome,
                    "connected": game_client.state.connected,
                }
            )

    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Web client for multiplayer RPS game")
    parser.add_argument("--server-host", default="127.0.0.1", help="RPS server host")
    parser.add_argument("--server-port", type=int, default=5555, help="RPS server port")
    parser.add_argument("--web-host", default="127.0.0.1", help="Flask web host")
    parser.add_argument("--web-port", type=int, default=5000, help="Flask web port")
    args = parser.parse_args()

    app = create_app(args.server_host, args.server_port)
    app.run(host=args.web_host, port=args.web_port, debug=False)
