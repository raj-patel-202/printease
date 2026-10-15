## 3. Printer PC Setup (`printer-pc/`)

This step is done on the Windows computer physically connected (via USB or LAN) to the printer.

### Files inside `printer-pc/`:
- `PrintEaseAgent.exe`: Pre-compiled background agent that receives print jobs from the server and prints them.
- `agent_config.example.json`: Safe configuration template committed to GitHub.
- `agent_config.json`: Your local configuration, ignored by Git because it contains the agent token.

### How to Configure and Run:

1. **Copy `agent_config.example.json` to `agent_config.json`, then configure it:**
   Open `printer-pc/agent_config.json` in a text editor (e.g., Notepad):
   ```json
   {
     "server_url": "http://localhost:8000",
     "agent_token": "your_secure_agent_token_here"
   }
   ```
   - `server_url`: Address of your running PrintEase server.
     - **Same PC as server:** Use `http://localhost:8000`.
     - **Separate PC on the same network (LAN):** Use the server machine's local IP (e.g., `http://192.168.1.50:8000`). *(Do not use `localhost` when running on a separate machine).*
     - **Cloud / VPS:** Use your server domain or public IP (e.g., `https://print.yourdomain.com`).
   - `agent_token`: Must exactly match the `AGENT_TOKEN` set in the server's `.env` file.

> [!NOTE]
> **If running on a separate PC across the local network:**
> - Ensure the server PC allows inbound connections on port 8000 through the Windows Defender Firewall:
>   ```powershell
>   New-NetFirewallRule -DisplayName "PrintEase Port 8000" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
>   ```

2. **Run the Agent:**
   - Double-click `PrintEaseAgent.exe`.
   - If Windows SmartScreen shows a warning (*"Windows protected your PC"*), click **More info** -> **Run anyway**.
   - The application will start and minimize to the **Windows System Tray** (bottom-right corner of the taskbar, near the clock).

3. **Select Your Printer:**
   - Right-click the PrintEase icon in the Windows System Tray.
   - Hover over **Printer** and select your desired printer from the list of installed Windows printers.
   - The agent will start polling the server and automatically print incoming orders.

4. **Start with Windows (Optional):**
   - Right-click the PrintEase icon in the System Tray and select **Start with Windows** (a checkmark `✓` will indicate it is active).
   - The agent will now automatically launch on system boot.

---

## 4. Admin Dashboard & Print Queue Management

Access the admin dashboard at:
👉 **`http://localhost:8000/admin/dashboard`**

### Features:
- **Printer Status:** Real-time visibility into whether the printer agent is currently online or offline, and which printer is actively selected.
- **Start / Stop Receiving Jobs:**
  - Click **Stop receiving jobs** to pause dispatching jobs (useful during paper/toner refills or printer maintenance).
  - Click **Start receiving jobs** to resume automated printing.
- **Manage Orders:** Monitor active print jobs, retry failed prints, preview uploaded PDFs, and mark completed jobs as delivered (which securely deletes the file from disk).
