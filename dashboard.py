import streamlit as st
import pandas as pd
import time
import os
import plotly.graph_objects as go
from datetime import datetime
from mock_inverter import MockSolarman
# We will import PySolarmanV5 only if needed to avoid errors if not installed/configured
# but for type safety or structure, we might need a wrapper.

# --- LOAD CONFIGURATION ---
def load_config():
    config = {
        "MODE": "mock",
        "INVERTER_IP": "127.0.0.1",
        "INVERTER_SN": 0,
        "INVERTER_PORT": 8899,
        "REFRESH_RATE": 5
    }
    if os.path.exists("config.txt"):
        with open("config.txt", "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"): continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    config[key.strip()] = value.strip()
    return config

CONFIG = load_config()

# Set page config
st.set_page_config(
    page_title=f"Waaree Solar Dashboard ({CONFIG['MODE'].upper()})",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize Session State
if 'inverter' not in st.session_state:
    if CONFIG["MODE"].lower() == "real":
        try:
            from pysolarmanv5 import PySolarmanV5
            # We need a wrapper to match the get_sensors() interface of MockSolarman
            class RealSolarmanWrapper:
                def __init__(self, ip, sn, port):
                    try:
                        sn_int = int(sn)
                    except ValueError:
                        st.warning(f"⚠️ Warning: Serial Number '{sn}' is alphanumeric. Solarman V5 usually requires an Integer SN (e.g. 170xxxxxxx). attempting to proceed, but connection may fail.")
                        # Some implementations might handle strings by hashing or partial use, but pysolarmanv5 expects int.
                        # We will pass 0 if conversion fails to let library decide, or raise error.
                        sn_int = 0 
                    
                    self.modbus = PySolarmanV5(ip, sn_int, port=int(port), verbose=True)
                
                def get_sensors(self):
                    # NOTE: You MUST map these registers to your specific inverter model.
                    # These are generic Waaree/Solis placeholder registers.
                    # You might need to adjust offsets.
                    
                    # Reading a block of registers. 
                    # Assuming Grid Voltage is around 0x0400 (1024)
                    grid_data = self.modbus.read_holding_registers(register_addr=1024, quantity=10)
                    
                    # Assuming PV Generation is around 0x0500 (1280) or similar
                    # This is highly model dependent.
                    # For V5 dongles, sometimes we just read a massive block.
                    
                    # Let's try reading a known block for AC parameters
                    # Just an example mapping!
                    voltage = grid_data[0] * 0.1
                    current = grid_data[1] * 0.1
                    freq = grid_data[4] * 0.01
                    
                    return {
                        "timestamp": datetime.now().strftime("%H:%M:%S"),
                        "status": "Online",
                        "pv_power": 0, # Need register for this
                        "gen_today": 0,
                        "gen_total": 0,
                        "grid_voltage": round(voltage, 1),
                        "grid_freq": round(freq, 2),
                        "inv_temp": 0,
                        "pv1_voltage": 0,
                        "pv1_current": 0,
                        "pv2_voltage": 0,
                        "pv2_current": 0,
                    }
            
            st.session_state.inverter = RealSolarmanWrapper(
                CONFIG["INVERTER_IP"], 
                CONFIG["INVERTER_SN"], 
                CONFIG["INVERTER_PORT"]
            )
            st.toast("Connected to Inverter!", icon="✅")
        except Exception as e:
            st.error(f"Failed to connect to inverter: {e}")
            st.session_state.inverter = MockSolarman() # Fallback
    else:
        st.session_state.inverter = MockSolarman()
    
    st.session_state.history = []

# Sidebar Configuration
st.sidebar.title("☀️ Solar Monitor")
mode_label = "SIMULATION" if CONFIG["MODE"] == "mock" else "LIVE DATA"
st.sidebar.success(f"Mode: {mode_label}")
if CONFIG["MODE"] == "real":
    st.sidebar.info(f"IP: {CONFIG['INVERTER_IP']}\nS/N: {CONFIG['INVERTER_SN']}")

refresh_rate = st.sidebar.slider("Refresh Rate (seconds)", 1, 30, int(CONFIG["REFRESH_RATE"]))
auto_refresh = st.sidebar.checkbox("Auto Refresh", value=True)

# Main Dashboard
st.title("My Home Solar Dashboard")

# Placeholder for metrics
metrics_container = st.container()
chart_container = st.container()

# Function to update data
def update_dashboard():
    # Fetch Data
    data = st.session_state.inverter.get_sensors()
    
    # Update History
    st.session_state.history.append(data)
    # Keep last 100 points
    if len(st.session_state.history) > 100:
        st.session_state.history.pop(0)
    
    # 1. Top Metrics Row
    with metrics_container:
        # Create 4 columns
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)

        # Solar Power
        kpi1.metric(
            label="Current Solar Power",
            value=f"{data['pv_power']} W",
            delta=f"{data['status']}",
        )

        # Daily Yield
        kpi2.metric(
            label="Daily Yield",
            value=f"{data['gen_today']} kWh",
            delta="Today"
        )
        
        # Grid Voltage
        kpi3.metric(
            label="Grid Voltage",
            value=f"{data['grid_voltage']} V",
            delta=f"{data['grid_freq']} Hz",
            delta_color="off"
        )

        # Inverter Temp
        kpi4.metric(
            label="Inverter Temp",
            value=f"{data['inv_temp']} °C",
            delta="Normal" if data['inv_temp'] < 50 else "High",
            delta_color="inverse"
        )

    # 2. Charts
    with chart_container:
        df = pd.DataFrame(st.session_state.history)
        
        # Plotly Line Chart for Power
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            y=df['pv_power'],
            mode='lines+markers',
            name='PV Power (W)',
            line=dict(color='#FFD700', width=3),
            fill='tozeroy'
        ))
        
        fig.update_layout(
            title="Real-time Power Generation",
            xaxis_title="Time (Last 100 Ticks)",
            yaxis_title="Watts",
            height=400,
            template="plotly_dark",
            margin=dict(l=20, r=20, t=40, b=20)
        )
        
        st.plotly_chart(fig, use_container_width=True)

        # Detailed Data Table (Expandable)
        with st.expander("📋 View Detailed Telemetry"):
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("PV Input")
                st.write(f"**PV1 Voltage:** {data['pv1_voltage']} V")
                st.write(f"**PV1 Current:** {data['pv1_current']} A")
            with col2:
                st.subheader("PV Input 2")
                st.write(f"**PV2 Voltage:** {data['pv2_voltage']} V")
                st.write(f"**PV2 Current:** {data['pv2_current']} A")
                
            st.dataframe(df.tail(5))

# Loop for auto-refresh
if auto_refresh:
    update_dashboard()
    time.sleep(refresh_rate)
    st.rerun()
else:
    update_dashboard()
