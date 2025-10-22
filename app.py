import streamlit as st
import json
from pathlib import Path
import random

DATA_FILE = Path("pickleball_data.json")

# ---------------------------
# Helpers for persistent storage
# ---------------------------

def load_json(file_path):
    if not file_path.exists():
        return {"players": [], "queue": [], "courts": [[], [], []], "streaks": {}, "history": [], "auto_fill": False}
    with open(file_path, "r") as f:
        return json.load(f)

def save_json(file_path, data):
    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)

# Initialize session state
if "initialized" not in st.session_state:
    st.session_state.initialized = True
    data = load_json(DATA_FILE)
    st.session_state.data = data
else:
    data = st.session_state.data

# ---------------------------
# Utility functions
# ---------------------------

def reset_everything():
    st.session_state.data = {
        "players": [],
        "queue": [],
        "courts": [[], [], []],
        "streaks": {},
        "history": [],
        "auto_fill": False
    }
    save_json(DATA_FILE, st.session_state.data)
    st.success("All data reset!")

def assign_all_courts():
    """Fill each empty court with 4 players (2v2) from the queue."""
    data = st.session_state.data
    queue = data["queue"]
    courts = data["courts"]

    for i in range(len(courts)):
        if len(courts[i]) < 4 and len(queue) >= 4:
            courts[i] = [queue.pop(0) for _ in range(4)]

    save_json(DATA_FILE, data)

def auto_fill_if_enabled():
    """Automatically fill courts if Auto-Fill mode is active."""
    if st.session_state.data.get("auto_fill", False):
        assign_all_courts()

def submit_winner(court_index, winning_team):
    """Handle winners/losers and enforce the two-game limit."""
    data = st.session_state.data
    court_players = data["courts"][court_index]
    if len(court_players) != 4:
        return

    team1 = court_players[:2]
    team2 = court_players[2:]

    winners = team1 if winning_team == 1 else team2
    losers = team2 if winning_team == 1 else team1

    # Increment streaks for winners, reset for losers
    for player in winners:
        data["streaks"][player] = data["streaks"].get(player, 0) + 1
    for player in losers:
        data["streaks"][player] = 0

    # Check for 2-game limit
    staying_players = [p for p in winners if data["streaks"].get(p, 0) < 2]
    leaving_players = [p for p in winners if data["streaks"].get(p, 0) >= 2]

    # Always move losers + over-limit winners to back of queue
    for player in losers + leaving_players:
        if player not in data["queue"]:
            data["queue"].append(player)
        data["streaks"][player] = 0

    # Bring in replacements
    while len(staying_players) < 2 and len(data["queue"]) > 0:
        staying_players.append(data["queue"].pop(0))

    new_players = []
    while len(new_players) < 2 and len(data["queue"]) > 0:
        new_players.append(data["queue"].pop(0))

    court_players_new = staying_players + new_players
    random.shuffle(court_players_new)
    data["courts"][court_index] = court_players_new
    save_json(DATA_FILE, data)

    auto_fill_if_enabled()  # auto-fill after game if toggle on

def reset_single_court(court_index):
    """Clears one court and moves its players to the back of the queue."""
    data = st.session_state.data
    court_players = data["courts"][court_index]
    for player in court_players:
        data["streaks"][player] = 0
        if player not in data["queue"]:
            data["queue"].append(player)
    data["courts"][court_index] = []
    save_json(DATA_FILE, data)
    auto_fill_if_enabled()

def reset_all_courts():
    """Moves all active players from all courts to the end of the queue."""
    data = st.session_state.data
    for i in range(len(data["courts"])):
        court_players = data["courts"][i]
        for player in court_players:
            data["streaks"][player] = 0
            if player not in data["queue"]:
                data["queue"].append(player)
        data["courts"][i] = []
    save_json(DATA_FILE, data)
    auto_fill_if_enabled()
    st.success("All courts reset — players moved to back of queue.")

# ---------------------------
# Streamlit UI
# ---------------------------

st.title("🏓 Pickleball Open Play Scheduler")
page = st.sidebar.radio("Navigation", ["Config / Player Setup", "Court Management"])

# ---------------------------
# CONFIG PAGE
# ---------------------------

if page == "Config / Player Setup":
    st.header("Player & Queue Setup")

    st.write("Add multiple players at once (one name per line):")
    bulk_input = st.text_area("Enter player names", height=150, placeholder="Player 1\nPlayer 2\nPlayer 3...")
    if st.button("Add Players"):
        new_players = [p.strip() for p in bulk_input.splitlines() if p.strip()]
        for player in new_players:
            if player not in data["players"]:
                data["players"].append(player)
                data["queue"].append(player)
                data["streaks"][player] = 0
        save_json(DATA_FILE, data)
        st.success(f"Added {len(new_players)} players.")

    st.toggle("Auto-Fill Courts Continuously", key="auto_fill", value=data.get("auto_fill", False))
    data["auto_fill"] = st.session_state.auto_fill
    save_json(DATA_FILE, data)

    if st.button("Clear All Data"):
        reset_everything()

    st.subheader("Current Players")
    st.write(data["players"])

    st.subheader("Current Queue (Top → Bottom)")
    st.write(data["queue"])

# ---------------------------
# COURT MANAGEMENT PAGE
# ---------------------------

elif page == "Court Management":
    st.header("Court Assignments")
    num_courts = len(data["courts"])

    if st.button("Assign all empty courts"):
        assign_all_courts()
        st.success("Courts filled from queue.")

    st.divider()
    st.subheader("Active Courts")

    for i in range(num_courts):
        court_players = data["courts"][i]
        st.markdown(f"### Court {i + 1}")

        if len(court_players) == 0:
            st.info("Empty court")
        else:
            col1, col2 = st.columns(2)
            col1.write("Team 1:")
            col1.write(court_players[:2])
            col2.write("Team 2:")
            col2.write(court_players[2:])

            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button(f"Team 1 Wins (Court {i + 1})"):
                    submit_winner(i, 1)
                    st.success(f"Team 1 Wins on Court {i + 1}")
            with col2:
                if st.button(f"Team 2 Wins (Court {i + 1})"):
                    submit_winner(i, 2)
                    st.success(f"Team 2 Wins on Court {i + 1}")
            with col3:
                if st.button(f"Reset Court {i + 1}"):
                    reset_single_court(i)
                    st.info(f"Court {i + 1} reset.")

        st.divider()

    if st.button("Reset All Courts"):
        reset_all_courts()

    st.subheader("Queue (Next Up)")
    st.write(data["queue"])
