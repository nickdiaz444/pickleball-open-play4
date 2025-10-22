import streamlit as st
import json
from pathlib import Path
import pandas as pd

DATA_FILE = Path("pickleball_data.json")

# ---------------------------
# Helpers for persistent storage
# ---------------------------
def load_json(file_path):
    if not file_path.exists():
        return {
            "players": [],
            "queue": [],
            "courts": [[], [], []],
            "streaks": {},
            "history": [],
            "auto_fill": False
        }
    with open(file_path, "r") as f:
        return json.load(f)

def save_json(file_path, data):
    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)

# ---------------------------
# Initialize session state
# ---------------------------
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
    data = st.session_state.data
    queue = data["queue"]
    courts = data["courts"]
    for i in range(len(courts)):
        if len(courts[i]) < 4 and len(queue) >= 4:
            courts[i] = [queue.pop(0) for _ in range(4)]
    save_json(DATA_FILE, data)

def auto_fill_if_enabled():
    if st.session_state.data.get("auto_fill", False):
        assign_all_courts()

def process_court_winner(court_index, winning_team):
    data = st.session_state.data
    court_players = data["courts"][court_index]
    if len(court_players) != 4:
        return

    team1 = court_players[:2]
    team2 = court_players[2:]

    winners = team1 if winning_team == "Team 1" else team2
    losers = team2 if winning_team == "Team 1" else team1

    # Determine staying winners and leaving winners (max 2 games)
    staying_winners = [p for p in winners if data["streaks"].get(p,0) < 2]
    leaving_winners = [p for p in winners if data["streaks"].get(p,0) >= 2]

    # Increment streaks for staying winners
    for player in staying_winners:
        data["streaks"][player] = data["streaks"].get(player,0) + 1

    # Reset streaks for leaving winners and losers; send to back of queue
    for player in losers + leaving_winners:
        data["streaks"][player] = 0
        if player not in data["queue"]:
            data["queue"].append(player)

    # Fill court up to 4 players from queue
    needed = 4 - len(staying_winners)
    new_players = []
    for _ in range(needed):
        if len(data["queue"]) > 0:
            new_players.append(data["queue"].pop(0))

    data["courts"][court_index] = staying_winners + new_players

    # Record in history
    data["history"].append({
        "court": court_index + 1,
        "team_won": winning_team,
        "players": court_players.copy()
    })

def update_all_courts():
    for i in range(len(data["courts"])):
        winner = st.session_state.get(f"court_winner_{i}", "")
        if winner in ["Team 1", "Team 2"]:
            process_court_winner(i, winner)
            st.session_state[f"court_winner_{i}"] = ""  # clear selection
    save_json(DATA_FILE, data)
    auto_fill_if_enabled()
    st.success("All courts updated!")

def reset_single_court(court_index):
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
    for i in range(len(data["courts"])):
        reset_single_court(i)
    st.success("All courts reset — players moved to back of queue.")

# ---------------------------
# Sidebar Config
# ---------------------------
st.sidebar.header("⚙️ Configuration")
st.session_state.data["auto_fill"] = st.sidebar.checkbox("Auto-Fill Courts Continuously", value=data.get("auto_fill", False))

if st.sidebar.button("Reset All Data"):
    reset_everything()
if st.sidebar.button("Reset All Courts"):
    reset_all_courts()

with st.sidebar.expander("Player Management"):
    st.write("Add multiple players at once (one per line):")
    bulk_input = st.text_area("Enter player names", height=150, placeholder="Player 1\nPlayer 2\nPlayer 3...")
    if st.button("Add Players", key="add_players_sidebar"):
        new_players = [p.strip() for p in bulk_input.splitlines() if p.strip()]
        for player in new_players:
            if player not in data["players"]:
                data["players"].append(player)
                data["queue"].append(player)
                data["streaks"][player] = 0
        save_json(DATA_FILE, data)
        st.success(f"Added {len(new_players)} players.")

# ---------------------------
# Main Page
# ---------------------------
st.title("🏓 Pickleball Open Play Scheduler")
tabs = st.tabs(["Courts", "Queue", "History"])

# ---------------------------
# Courts Tab
# ---------------------------
with tabs[0]:
    st.subheader("Active Courts")
    num_courts = len(data["courts"])

    if st.button("Assign all empty courts"):
        assign_all_courts()
        st.success("Courts filled from queue.")
    st.divider()

    for i in range(num_courts):
        court_players = data["courts"][i]
        st.markdown(f"### Court {i + 1}")

        if len(court_players) == 0:
            st.info("Empty court")
        else:
            col1, col2 = st.columns(2)
            col1.markdown(f"**Team 1:** {', '.join(court_players[:2])}")
            col2.markdown(f"**Team 2:** {', '.join(court_players[2:])}")

            # Winner dropdown with persistent key
            winner_key = f"court_winner_{i}"
            if winner_key not in st.session_state:
                st.session_state[winner_key] = ""
            st.session_state[winner_key] = st.selectbox(
                f"Select winner (Court {i + 1})",
                ["", "Team 1", "Team 2"],
                index=["", "Team 1", "Team 2"].index(st.session_state[winner_key]),
                key=winner_key+"_selectbox"
            )

            col1b, col2b = st.columns(2)
            with col1b:
                if st.button(f"Reset Court {i + 1}", key=f"reset_{i}"):
                    reset_single_court(i)
                    st.info(f"Court {i + 1} reset.")

    if st.button("Update All Courts"):
        update_all_courts()

# ---------------------------
# Queue Tab
# ---------------------------
with tabs[1]:
    st.subheader("Queue (Next Up)")
    st.write(", ".join(data["queue"]))

# ---------------------------
# History Tab
# ---------------------------
with tabs[2]:
    st.subheader("Game History")
    if data["history"]:
        history_rows = []
        for entry in data["history"]:
            history_rows.append({
                "Court": entry["court"],
                "Winner": entry["team_won"],
                "Player 1": entry["players"][0],
                "Player 2": entry["players"][1],
                "Player 3": entry["players"][2],
                "Player 4": entry["players"][3],
            })
        df_history = pd.DataFrame(history_rows)
        st.dataframe(df_history)
    else:
        st.info("No games played yet.")
