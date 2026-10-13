# PrintEase (Smart Printing Service)

PrintEase is a modern, web-based remote printing platform built with FastAPI. It allows users to upload documents, configure print settings (copies, color mode, paper size, duplex), pay via Razorpay, and automatically routes print jobs to a remote physical printer via a standalone Windows system tray client.

---

## ⚡ What's New: The Next-Gen Printer PC Pipeline

We completely redesigned the printer client (`printer_pc`) to be seamless and frictionless for shop operators:

- 🚫 **No Tailscale or VPN Required:** The client connects **outbound** over standard HTTP/HTTPS to your hosted server. You never need to set up Tailscale, configure port forwarding, or deal with firewall rules.
- 🚫 **Zero Python Setup:** The printer operator does **not** need Python, virtual environments, pip packages, or terminal commands.
- 📦 **Single Executable + Config:** Everything is pre-compiled into a standalone executable (`PrintEaseAgent.exe`) and a simple JSON configuration file (`agent_config.json`) inside `printer_pc/dist/`.
- 🖨️ **Windows System Tray App:** The agent lives quietly in the Windows system tray (taskbar notification area). The operator can simply right-click the tray icon to select their active printer from a list of all detected Windows printers.
- 🚀 **Windows Startup Support:** Option to launch on boot so printing works automatically every morning without operator intervention.
- 🎛️ **Remote Control via Admin Dashboard:** The shop admin can monitor the printer status and remotely pause or resume the print queue with a single click.

---

## 🏗 Architecture Overview

The system utilizes an outbound pull-based architecture:

```
┌─────────────────────────────────┐
│        PrintEase Server         │
│  (FastAPI + PostgreSQL Backend) │
└─────────────────────────────────┘
      ▲                       ▲
      │ Polling               │ Remote Start/Stop
      │ (Outbound HTTP)       │ & Queue Monitor
      │                       │
┌──────────────────────┐  ┌────────────────────────┐
│  Windows Printer PC  │  │    Admin Dashboard     │
│  System Tray Client  │  │  (Web Browser Console) │
│ (PrintEaseAgent.exe) │  └────────────────────────┘
└──────────────────────┘
      │
      ▼
┌──────────────────────┐
│ Selected Tray Printer│
│ (Local USB / Network)│
└──────────────────────┘
```

1. **Central Server:** Manages document validation, Razorpay payments, database records, and exposes the agent polling endpoints (`/api/agent/*`).
2. **Printer Client (`printer_pc/dist/`):** The Windows desktop system tray application running on the printer PC. It polls `/api/agent/next`, downloads the PDF, sends it to the user's selected system tray printer, and reports the result.
3. **Admin Dashboard:** Web console for the shop administrator to monitor agent connectivity, see which printer is selected, and remotely toggle the print queue on or off.

---

## 🖨️ Printer Operator Guide (`printer_pc`)

Setting up the printer PC requires **no developer skills or command-line tools**.

### 1. Requirements on the Printer PC
- Windows 10 or 11
- Physical printer connected and installed in Windows (USB, Wi-Fi, or Network)
- **No Python or dependencies needed!**

### 2. Quick Setup

1. **Get the Client Files:**
   Copy the `printer_pc/dist` folder to the printer machine. It contains:
   - `PrintEaseAgent.exe`
   - `agent_config.json`

2. **Set the Server URL:**
   Open `agent_config.json` in Notepad:
   ```json
   {
     "server_url": "https://your-printease-server.com",
     "agent_token": "your_secure_agent_token"
   }
   ```
   - Enter your hosted server's URL in `server_url` (or `http://localhost:8000` for local dev).
   - Enter the `agent_token` provided by the server administrator (matches `AGENT_TOKEN` in `.env`).
   - Save and close the file.

3. **Initialize the Agent:**
   Double-click `PrintEaseAgent.exe`.
   - The application starts and places an icon in the **Windows System Tray** (bottom-right corner near the clock).

4. **Select Your Printer in System Tray:**
   - Click the System Tray arrow near the clock to find the **PrintEase** icon.
   - Right-click the icon to view the menu:
     - **Select Printer:** Choose the target physical printer from the list of installed Windows printers.
     - **Status:** View current connection status (Connected / Polling).
     - **Exit:** Quit the agent.
   - The agent remembers your printer selection and immediately starts processing incoming orders!

---

## 🔄 Run on Windows Startup (Recommended)

To ensure the agent starts automatically whenever the printer PC turns on or reboots:

1. Press <kbd>Win</kbd> + <kbd>R</kbd> to open the Run window.
2. Type `shell:startup` and press **Enter**.
3. Right-click inside the folder and choose **New > Shortcut**.
4. Browse to where `PrintEaseAgent.exe` is located and click **Next** → **Finish**.

Now, whenever the PC boots up, the agent will silently start in the system tray, connect to the hosted server, and be ready to print.

---

## 🎛️ Admin Dashboard Controls

The shop administrator can manage everything remotely from the web browser at `/admin/dashboard`:

- **Real-Time Agent Status:**
  - 🟢 **Receiving jobs - Agent online (Printer Name)**: The tray client is connected, active, and shows the printer selected in the system tray.
  - 🟡 **Started - waiting for agent**: Queue is running, waiting for the agent to poll.
  - 🔴 **Stopped**: Print queue is paused.
- **One-Click Start / Pause:**
  - Click **"Stop receiving jobs"** to temporarily pause printing (useful when changing paper, adding ink, or closing shop).
  - Click **"Start receiving jobs"** to resume printing pending orders.
- **Order Management:**
  - Monitor job lifecycle (`pending` → `printing` → `completed`).
  - Retry failed jobs with one click.
  - Download or preview PDFs.
  - Mark prints as delivered (automatically purges the document from server storage).

---

## 🚀 Server Setup & Deployment

### Prerequisites
- [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/)
- Python 3.13 (only if running server locally without Docker)

### Environment Configuration (`.env`)

Create a `.env` file in the root directory:

```env
SECRET_KEY=your_secure_secret_key_here
COOKIE_SECURE=False

POSTGRES_USER=printeaseadmin
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=printease
DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}

RAZORPAY_API_KEY=your_razorpay_key
RAZORPAY_API_SECRET=your_razorpay_secret
RAZORPAY_WEBHOOK_SECRET=your_webhook_secret

WEB3FORMS_ACCESS_KEY=your_web3forms_key
CURRENCY=INR

# Token shared with the printer PC client in agent_config.json
AGENT_TOKEN=your_secure_agent_token_here
```

### Starting the Server

```bash
docker compose up --build -d
```
The server will be live at `http://localhost:8000`.

### Creating an Admin Account

```bash
# If running via Docker
docker compose exec web python create_admin.py

# If running locally
python create_admin.py
```

---

## 📂 Project Structure

```
printease/
├── authentication/             # JWT auth & Argon2 password hashing
├── models/                     # SQLAlchemy models & async DB engine
├── printer_pc/
│   └── dist/                   # Standalone client distribution
│       ├── PrintEaseAgent.exe  # Standalone Windows system tray executable
│       ├── agent_config.json   # Server URL and authentication token
│       └── agent_config.example.json # Example config template
├── routers/
│   ├── admin.py                # Admin dashboard & queue start/stop API
│   ├── agent.py                # Agent polling, file delivery & status endpoints
│   ├── orders.py               # Document upload and print configuration
│   ├── payments.py             # Razorpay checkout & webhook validation
│   └── users.py                # Customer authentication & account settings
├── schemas/                    # Pydantic validation schemas
├── services/
│   ├── payment_service.py      # Razorpay payment & refund processing
│   └── print_dispatcher.py     # In-memory queue dispatcher & timeout reaper
├── static/                     # Frontend CSS, JS, and icons
├── templates/                  # Jinja2 HTML templates
├── utils/                      # Validation, rate limiting & cost calculations
├── config.py                   # Pydantic settings management
├── create_admin.py             # Admin account creation utility
├── docker-compose.yml          # Container configuration
├── Dockerfile                  # Web service Docker container
└── requirements.txt            # Python server dependencies
```
