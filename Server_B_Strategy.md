# Server B Configuration Finder

We have confirmed the following:
1.  **API Auth Works**: We can login to `/api/v1/login` with password `12345678`.
2.  **Modbus Port Closed**: Port 8899 is closed (`ConnectionRefused`).
3.  **Data Endpoints Silent**: Standard endpoints like `get_meter_info`, `get_status` return empty JSON `{}`. This is likely because the device is in **Transparent Mode (DTU_STA=4)**, passing data directly to the cloud without local caching.
4.  **No Hidden HTML**: Common configuration HTML pages are missing (404).

## Strategy: Redirect Data to Local Server (Server B)

Since the device pushes data out, we need to configure it to push to **US** (your local machine) in addition to the cloud (Server A). This is often done via "Server B" configuration. we know `set_port` exists and accepts values 1-5. We suspect one of these ports corresponds to "Server B".

### Action Plan
1.  Find the API command to **SET** the remote server address. It is likely `set_server_info` or embedded in `set_network_info`.
2.  Once found, configure Server B (Port 2) to point to your computer's IP on port 10000.
3.  Run a simple Python TCP listener on your computer to receive and decode the Solarman V5 protocol data.

**Warning**: Changing server settings carries a small risk of disconnecting the device from the cloud if we overwrite Server A (Port 1). We should target Port 2.
