import random
import time
from datetime import datetime

class MockSolarman:
    """
    Simulates a Solarman generic inverter connection.
    Generates realistic looking data for a 5kW solar system.
    """
    def __init__(self):
        self._connected = True
        # Base values for simulation
        self.daily_yield = 15.4  # kWh starts here
        self.total_yield = 4500.0 # kWh
        
    def read_holding_registers(self, register_addr, quantity):
        """
        Simulates reading registers. 
        We will map ranges to specific dummy data categories.
        """
        # Get current time to simulate realistic curve
        now = datetime.now()
        hour = now.hour + (now.minute / 60)
        
        # Simulating a bell curve for solar production (6am to 6pm)
        if 6 <= hour <= 18:
            peak_power = 4500 # Watts
            # Simple parabola for sun path
            factor = 1 - ((hour - 12) / 6) ** 2
            if factor < 0: factor = 0
            current_power = peak_power * factor * random.uniform(0.9, 1.0)
        else:
            current_power = 0

        # Register Map Simulation (Generic Solarman/Solis/Waaree map)
        # Based on common offsets.
        
        # Scenario: Asking for Grid Output details (AC)
        # Often around register 3000-3040 or similar.
        # But `pysolarmanv5` user might query specific blocks.
        
        # We will return a list of integers as the real library does.
        # Modbus registers are 16-bit integers.
        
        data = []
        for i in range(quantity):
            # Generating somewhat random noise
            data.append(0)

        # Let's populate specific indices assuming the user requested a known block
        # For this dashboard, we will abstract the raw registers into a dictionary
        # in the main app, checking discrete "mock" calls.
        
        return [int(x) for x in data]

    def get_sensors(self):
        """
        Returns a dictionary of parsed values directly, skipping the register decoding 
        step for the sake of the mock dashboard.
        """
        now = datetime.now()
        hour = now.hour + (now.minute / 60)
        
        # 1. Solar Power (PV)
        if 6 <= hour <= 18:
            # Bell curve factor
            factor = max(0, 1 - ((hour - 12) / 6) ** 2)
            # Add some cloud noise
            noise = random.uniform(0.85, 1.0) if random.random() > 0.8 else 1.0
            pv_power_watts = 5000 * factor * noise
        else:
            pv_power_watts = 0

        # 2. Grid Voltage (AC) - Single phase usually 230V +- fluctuations
        grid_voltage = 230 + random.uniform(-5, 5)
        
        # 3. Frequency
        grid_freq = 50 + random.uniform(-0.05, 0.05)
        
        # 4. Temperature
        # Heat up during the day
        inv_temp = 25 + (pv_power_watts / 5000) * 20
        
        # 5. Yields
        # Increment daily yield slightly if power > 0
        if pv_power_watts > 0:
            self.daily_yield += (pv_power_watts / 1000) * (5/3600) # 5 seconds chunk
            self.total_yield += (pv_power_watts / 1000) * (5/3600)

        return {
            "timestamp": now.strftime("%H:%M:%S"),
            "status": "Generating" if pv_power_watts > 50 else "Standby",
            "pv_power": round(pv_power_watts, 2),        # Watts
            "gen_today": round(self.daily_yield, 2),     # kWh
            "gen_total": round(self.total_yield, 1),     # kWh
            "grid_voltage": round(grid_voltage, 1),      # Volts
            "grid_freq": round(grid_freq, 2),            # Hz
            "inv_temp": round(inv_temp, 1),              # Celsius
            "pv1_voltage": round(350 * (1 if pv_power_watts > 0 else 0), 1),
            "pv1_current": round((pv_power_watts/2)/350 if pv_power_watts > 0 else 0, 2),
            "pv2_voltage": round(350 * (1 if pv_power_watts > 0 else 0), 1),
            "pv2_current": round((pv_power_watts/2)/350 if pv_power_watts > 0 else 0, 2),
        }
