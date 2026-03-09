import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="F1 2026 Data Explorer", layout="wide")

# --- API HELPER ---
def GetF1Data(endpoint, params=None):
    try:
        base_url = "https://api.openf1.org/v1/"
        response = requests.get(f"{base_url}{endpoint}", params=params, timeout=5)
        return response.json()
    except:
        return []

# --- SIDEBAR: HISTORICAL VS LIVE ---
st.sidebar.header("📂 Session Selection")
mode = st.sidebar.radio("Mode", ["Live (2026)", "Historical"])

if mode == "Live (2026)":
    session_key = 'latest'
    st.sidebar.success("Tracking live 2026 session!")
else:
    # 1. Select Year
    year = st.sidebar.selectbox("Year", [2026, 2025, 2024], index=0)
    
    # 2. Select Meeting (The GP Weekend)
    meetings = GetF1Data("meetings", {"year": year})
    
    # 🛡️ CHECK: Is 'meetings' a valid list?
    if isinstance(meetings, list) and len(meetings) > 0:
        meeting_map = {m['meeting_key']: m['meeting_official_name'] for m in meetings}
        selected_meeting = st.sidebar.selectbox(
            "Grand Prix", 
            options=list(meeting_map.keys()), 
            format_func=lambda x: meeting_map[x]
        )
        
        # 3. Select Session (FP1, Quali, Race)
        sessions = GetF1Data("sessions", {"meeting_key": selected_meeting})
        
        # 🛡️ CHECK: Is 'sessions' a valid list?
        if isinstance(sessions, list) and len(sessions) > 0:
            session_map = {s['session_key']: f"{s['session_name']} ({s['date_start'][:10]})" for s in sessions}
            session_key = st.sidebar.selectbox(
                "Session Type", 
                options=list(session_map.keys()), 
                format_func=lambda x: session_map[x]
            )
        else:
            st.sidebar.warning("No sessions found for this meeting.")
            st.stop() # Stops the app from running further and crashing
    else:
        st.sidebar.error(f"No race data found for {year} yet.")
        st.stop()

# Fetch Drivers for this session (Do this outside fragment so it's only done once)
drivers_raw = GetF1Data("drivers", {"session_key": session_key})
driver_map = {d['driver_number']: d['broadcast_name'] for d in drivers_raw}

# --- FRAGMENT: LIVE TIMING & TELEMETRY (Refreshes every 3 seconds) ---
@st.fragment(run_every=3)
def render_live_data(s_key, d_map):
    st.title(f"🏎️ {mode} Dashboard")
    
    if not d_map:
        st.warning("No data found for this session yet.")
        return

    col1, col2 = st.columns([1, 1])

    # 1. STANDINGS
    with col1:
        st.subheader("🏁 Standings")
        positions = GetF1Data("position", {"session_key": s_key})
        if isinstance(positions, list) and len(positions) > 0:
            latest_pos = {}
            for p in positions:
                latest_pos[p['driver_number']] = p['position']
            
            standings_data = [{"Pos": pos, "Driver": d_map.get(num, "Unknown"), "Number": num} 
                             for num, pos in latest_pos.items()]
            
            df_standings = pd.DataFrame(standings_data).sort_values('Pos')
            st.table(df_standings[['Pos', 'Driver', 'Number']])
        else:
            st.info("Waiting for position data...")

    # 2. GRID TELEMETRY
    with col2:
        st.subheader("📊 Grid Telemetry")
        all_car_data = GetF1Data("car_data", {"session_key": s_key})
        
        if isinstance(all_car_data, list) and len(all_car_data) > 0:
            latest_ticks = {entry['driver_number']: entry for entry in all_car_data}
            grid_data = [{
                "Driver": d_map.get(num, f"Driver {num}"),
                "Speed": data.get('speed', 0),
                "Gear": data.get('n_gear', 0),
                "Thr %": data.get('throttle', 0),
                "Brk": "🔴" if data.get('brake', 0) > 0 else "⚪",
                "DRS": "🟢" if data.get('drs', 0) in [10, 12, 14] else "⚪"
            } for num, data in latest_ticks.items()]
            
            grid_df = pd.DataFrame(grid_data).sort_values(by="Speed", ascending=False)
            st.dataframe(grid_df, use_container_width=True, hide_index=True)
        else:
            st.info("Searching for live car data...")

# --- FRAGMENT: RADIO FEED (Refreshes every 30 seconds to avoid audio reset) ---
@st.fragment(run_every=30)
def render_radio_feed(s_key, d_map):
    st.divider() 
    st.subheader("🎧 Global Team Radio Feed")
    all_radios = GetF1Data("team_radio", {"session_key": s_key})

    if isinstance(all_radios, list) and len(all_radios) > 0:
        latest_radios = all_radios[-15:][::-1] # Last 15, reversed

        for msg in latest_radios:
            d_name = d_map.get(msg['driver_number'], f"Driver {msg['driver_number']}")
            timestamp = msg['date'][11:16]
            with st.expander(f"📢 {d_name} | {timestamp}"):
                st.audio(msg['recording_url'])
    else:
        st.info("No radio clips found.")

# --- RUN DASHBOARD ---
render_live_data(session_key, driver_map)
render_radio_feed(session_key, driver_map)