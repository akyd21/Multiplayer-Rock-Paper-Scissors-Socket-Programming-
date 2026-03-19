import socket
import threading


HOST = "0.0.0.0"
PORT = 5555

VALID_CHOICES = {"rock", "paper", "scissors"}


class RPSGameServer:
    """TCP socket server for a 2-player Rock-Paper-Scissors game."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        self.clients = []
        self.client_names = {}
        self.client_choices = {}

        self.lock = threading.Lock()
        self.round_number = 1
        self.running = True

    def start(self) -> None:
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(2)
        print(f"[SERVER] Listening on {self.host}:{self.port}")
        print("[SERVER] Waiting for 2 players to connect...")

        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
            except OSError:
                break

            with self.lock:
                if len(self.clients) >= 2:
                    self._send_line(client_socket, "ERROR Server full. Try again later.")
                    client_socket.close()
                    print(f"[SERVER] Rejected connection from {address} (server full).")
                    continue

                self.clients.append(client_socket)
                player_number = len(self.clients)
                player_name = f"Player {player_number}"
                self.client_names[client_socket] = player_name

            print(f"[SERVER] {player_name} connected from {address}")
            self._send_line(client_socket, f"WELCOME {player_name}")

            thread = threading.Thread(target=self._handle_client, args=(client_socket,), daemon=True)
            thread.start()

            with self.lock:
                if len(self.clients) == 2:
                    print("[SERVER] Both players connected. Starting game rounds.")
                    self._broadcast("START Both players connected. Send your move: rock, paper, or scissors.")

    def _send_line(self, sock: socket.socket, message: str) -> None:
        try:
            sock.sendall((message + "\n").encode("utf-8"))
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def _broadcast(self, message: str) -> None:
        for client in list(self.clients):
            self._send_line(client, message)

    def _handle_client(self, client_socket: socket.socket) -> None:
        buffer = ""
        while self.running:
            try:
                data = client_socket.recv(1024)
                if not data:
                    self._disconnect_client(client_socket)
                    return
            except (ConnectionResetError, OSError):
                self._disconnect_client(client_socket)
                return

            buffer += data.decode("utf-8", errors="ignore")
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                message = line.strip()
                if message:
                    self._process_message(client_socket, message)

    def _process_message(self, client_socket: socket.socket, message: str) -> None:
        parts = message.split(maxsplit=1)
        command = parts[0].upper()

        if command != "MOVE":
            self._send_line(client_socket, "ERROR Invalid command. Use: MOVE rock|paper|scissors")
            return

        if len(parts) != 2:
            self._send_line(client_socket, "ERROR Move missing. Example: MOVE rock")
            return

        choice = parts[1].strip().lower()
        if choice not in VALID_CHOICES:
            self._send_line(client_socket, "ERROR Invalid move. Choose rock, paper, or scissors.")
            return

        with self.lock:
            if len(self.clients) < 2:
                self._send_line(client_socket, "WAIT Waiting for second player...")
                return

            self.client_choices[client_socket] = choice
            player_name = self.client_names.get(client_socket, "Unknown")
            print(f"[SERVER] Round {self.round_number}: {player_name} chose {choice}")

            self._send_line(client_socket, f"ACK Choice received: {choice}")

            if len(self.client_choices) < 2:
                self._send_line(client_socket, "WAIT Waiting for opponent move...")
                return

            p1_socket = self.clients[0]
            p2_socket = self.clients[1]
            p1_choice = self.client_choices.get(p1_socket)
            p2_choice = self.client_choices.get(p2_socket)

            if not p1_choice or not p2_choice:
                return

            winner = self._determine_winner(p1_choice, p2_choice)
            print(
                f"[SERVER] Round {self.round_number} result: "
                f"Player 1 ({p1_choice}) vs Player 2 ({p2_choice}) -> {winner}"
            )

            self._send_round_result(p1_socket, p2_socket, p1_choice, p2_choice, winner)

            self.client_choices.clear()
            self.round_number += 1

    def _determine_winner(self, p1_choice: str, p2_choice: str) -> str:
        if p1_choice == p2_choice:
            return "Draw"

        wins_against = {
            "rock": "scissors",
            "paper": "rock",
            "scissors": "paper",
        }
        if wins_against[p1_choice] == p2_choice:
            return "Player 1"
        return "Player 2"

    def _send_round_result(
        self,
        p1_socket: socket.socket,
        p2_socket: socket.socket,
        p1_choice: str,
        p2_choice: str,
        winner: str,
    ) -> None:
        if winner == "Draw":
            p1_outcome = "Draw"
            p2_outcome = "Draw"
        elif winner == "Player 1":
            p1_outcome = "Win"
            p2_outcome = "Lose"
        else:
            p1_outcome = "Lose"
            p2_outcome = "Win"

        self._send_line(
            p1_socket,
            f"RESULT Round {self.round_number} | You: {p1_choice} | Opponent: {p2_choice} | Outcome: {p1_outcome}",
        )
        self._send_line(
            p2_socket,
            f"RESULT Round {self.round_number} | You: {p2_choice} | Opponent: {p1_choice} | Outcome: {p2_outcome}",
        )

        self._broadcast("NEXT Next round started. Send your move.")

    def _disconnect_client(self, client_socket: socket.socket) -> None:
        with self.lock:
            if client_socket in self.clients:
                player_name = self.client_names.get(client_socket, "Unknown")
                print(f"[SERVER] {player_name} disconnected.")

                self.clients.remove(client_socket)
                self.client_choices.pop(client_socket, None)
                self.client_names.pop(client_socket, None)

                self._broadcast("WAIT Opponent disconnected. Waiting for a new player...")

            try:
                client_socket.close()
            except OSError:
                pass

    def stop(self) -> None:
        self.running = False
        try:
            self.server_socket.close()
        except OSError:
            pass


if __name__ == "__main__":
    game_server = RPSGameServer(HOST, PORT)
    try:
        game_server.start()
    except KeyboardInterrupt:
        print("\n[SERVER] Shutting down...")
        game_server.stop()
