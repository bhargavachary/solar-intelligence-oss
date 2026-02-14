from pysolarmanv5 import PySolarmanV5

# CONFIGURATION
# You need to find your dongle's IP address.
# You can use a network scanner or check your router's client list.
INVERTER_IP = "192.168.1.50"      # <--- REPLACE THIS with your Dongle IP
INVERTER_SN = 2856234567          # <--- REPLACE THIS with your Dongle Serial Number (Integer)

def main():
    print(f"🔌 Connecting to {INVERTER_IP}...")
    try:
        modbus = PySolarmanV5(INVERTER_IP, INVERTER_SN, port=8899, verbose=True)
        
        # READING LIVE DATA
        # Note: Register addresses vary by model. 
        # Standard Waaree/Solis map often puts AC Power around 3000-3100 or 1000-1100.
        # Let's read the "Grid Voltage" (usually stable and easy to verify).
        # Register 0x0400 (1024) is a common starting point for Grid parameters.
        
        print("📥 Reading Registers...")
        # Reading 10 registers starting from 1024 (0x0400)
        data = modbus.read_holding_registers(register_addr=1024, quantity=10)
        
        # Example parsing (Check your specific inverter Modbus Map PDF)
        # Often: 
        # Index 0 (Reg 1024) = Grid Voltage R-Phase (x0.1 V)
        # Index 1 (Reg 1025) = Grid Current (x0.1 A)
        
        # Basic example calculation, adjust scale factor based on documentation
        voltage = data[0] * 0.1
        print(f"✅ SUCCESS! Connection Established.")
        print(f"⚡ Grid Voltage (approx): {voltage:.2f} V")
        print(f"📜 Raw Data Dump: {data}")

    except Exception as e:
        print(f"❌ FAILED: {e}")

if __name__ == "__main__":
    main()
