const joinBtn = document.getElementById("joinBtn");
const moveButtons = document.querySelectorAll(".move-btn");

const playerNameEl = document.getElementById("playerName");
const statusEl = document.getElementById("status");
const resultEl = document.getElementById("result");
const outcomeEl = document.getElementById("outcome");
const messageEl = document.getElementById("message");

function getTabClientId() {
    const key = "rps_client_id";
    let id = sessionStorage.getItem(key);
    if (id) {
        return id;
    }

    if (window.crypto && typeof window.crypto.randomUUID === "function") {
        id = window.crypto.randomUUID();
    } else {
        id = `client-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    }

    sessionStorage.setItem(key, id);
    return id;
}

const clientId = getTabClientId();

function setMoveButtonsEnabled(enabled) {
    moveButtons.forEach((button) => {
        button.disabled = !enabled;
    });
}

async function joinGame() {
    try {
        const response = await fetch("/api/join", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-Client-Id": clientId,
            },
        });
        const data = await response.json();

        if (!response.ok || !data.ok) {
            messageEl.textContent = data.error || "Could not join game.";
            return;
        }

        messageEl.textContent = "Connected to server. Waiting for game updates...";
    } catch (error) {
        messageEl.textContent = "Network error while joining game.";
    }
}

async function playMove(move) {
    const valid = ["rock", "paper", "scissors"];
    if (!valid.includes(move)) {
        messageEl.textContent = "Invalid move selected.";
        return;
    }

    try {
        const response = await fetch("/api/play", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-Client-Id": clientId,
            },
            body: JSON.stringify({ move }),
        });
        const data = await response.json();

        if (!response.ok || !data.ok) {
            messageEl.textContent = data.error || "Could not send move.";
            return;
        }

        messageEl.textContent = data.message;
    } catch (error) {
        messageEl.textContent = "Network error while sending move.";
    }
}

async function refreshState() {
    try {
        const response = await fetch("/api/state", {
            headers: {
                "X-Client-Id": clientId,
            },
        });
        const state = await response.json();

        playerNameEl.textContent = state.player;
        statusEl.textContent = state.status;
        resultEl.textContent = state.last_result || "No round result yet.";
        outcomeEl.textContent = state.last_outcome ? `Outcome: ${state.last_outcome}` : "";
        messageEl.textContent = state.last_message || messageEl.textContent;

        setMoveButtonsEnabled(Boolean(state.connected));
    } catch (error) {
        statusEl.textContent = "Disconnected";
        setMoveButtonsEnabled(false);
    }
}

joinBtn.addEventListener("click", joinGame);

moveButtons.forEach((button) => {
    button.addEventListener("click", () => {
        const move = button.dataset.move;
        playMove(move);
    });
});

setMoveButtonsEnabled(false);
setInterval(refreshState, 800);
refreshState();
