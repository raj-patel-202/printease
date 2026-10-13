# PrintEase (Smart Printing Service)

PrintEase is a modern, web-based remote printing solution built with FastAPI. It allows users to securely upload documents, configure print settings (copies, color mode, paper size, duplex), process payments via Razorpay, and automatically route jobs to a remotely connected physical printer via a standalone Windows agent.

---

## 🏗 Architecture Overview

The system is designed with a decoupled, pull-based architecture:

```
┌────────────────────────┐                   ┌──────────────────────────────────┐
│   PrintEase Server     │◄─── Outbound ─────│ Windows Printer PC               │
│ (FastAPI + PostgreSQL) │     Polling (HTTP)│ (Standalone PrintEaseAgent.exe)  │
└────────────────────────┘                   └──────────────────────────────────┘
            ▲                                                 │
            │ Manage Queue / Start / Stop                     ▼
┌────────────────────────┐                             ┌──────────────┐
│    Admin Dashboard     │                             │ Local Printer│
└────────────────────────┘                             └──────────────┘
```

1. **Central Server (Web Backend):** Handles user authentication, document validation, payment processing (Razorpay), database operations (PostgreSQL), and orchestrates the print queue.
2. **Printer Client (`printer_pc/`):** A standalone Windows agent (`PrintEaseAgent.exe`) with a single configuration file (`agent_config.json`). The agent connects **outbound** to the central server to pull print jobs. **No Python setup, no complex dependencies, and no inbound ports or Tailscale VPN tunnels are required on the printer PC.**
3. **Admin Dashboard:** Provides real-time visibility into the printer agent's connection status, current jobs, and gives shop administrators one-click remote control to start or pause the printing service.

---

## ✨ Features

- **User Authentication:** Secure registration and login using Argon2 password hashing and HTTP-only JWT cookies.
- **Document Upload & Validation:** Secure PDF uploads with strict file size, page counting, and format validation.
- **Dynamic Cost Calculation:** Automatic cost computation based on page count, color mode (B&W / Color), side mode (single / double-sided), and discounts.
- **Payment Gateway:** Secure checkout and webhook processing via Razorpay.
- **Standalone Windows Print Client:** A single pre-compiled `.exe` file designed for zero-friction setup by printer operators.
- **Outbound Pull Architecture:** The agent polls the server for jobs (`GET /api/agent/next`), downloading files and reporting results directly. Works behind any standard router/firewall without port forwarding or VPNs.
- **Admin Dashboard & Remote Controls:**
  - Real-time agent status monitor (Agent Online / Offline, detected printer hardware, active print job ID).
  - One-click Start / Stop button to pause or resume print job dispatching without accessing the physical printer PC.
  - Job retry mechanisms, PDF previews, and delivery marking with automated disk cleanup.
- **Windows Startup Support:** Can be configured to automatically launch on Windows boot for hands-off operation.

---

## 🚀 Getting Started (Server)

### Prerequisites

- [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/)
- Python 3.13 (if running locally without Docker)

### Environment Setup

Create a `.env` file in the root directory:

```env
SECRET_KEY=your_secret_key_here
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

# Secret token used by the printer PC agent to authenticate against the server
AGENT_TOKEN=your_secure_agent_token_here
```

### Running with Docker

Start the FastAPI application and PostgreSQL database with Docker Compose:

```bash
docker compose up --build -d
```

The web service will be accessible at `http://localhost:8000`.

### Creating an Admin Account

To access the admin dashboard, create an administrator profile:

```bash
# If running via Docker
docker compose exec web python create_admin.py

# If running locally
python create_admin.py
```

Follow the prompts to enter your admin email and password.

---

## 🖨 Setting up the Printer Client (`printer_pc`)

The client setup is streamlined for printer operators: **one `.exe` file and one `.json` config file.** No Python installation or command-line experience is required.

### Step 1: Copy Client Files to the Printer PC

Copy the contents of the `printer_pc/dist` folder to the Windows computer connected to your physical printer:
- `PrintEaseAgent.exe`
- `agent_config.json`

*(A template `agent_config.example.json` is also provided for reference.)*

### Step 2: Configure Server Connection

Open `agent_config.json` in Notepad or any text editor:

```json
{
  "server_url": "https://your-printease-server.com",
  "agent_token": "your_secure_agent_token_here"
}
```

- **`server_url`**: The URL where your PrintEase server is hosted (e.g., `http://localhost:8000` for local testing or `https://printease.yourdomain.com` for production).
- **`agent_token`**: Must match the `AGENT_TOKEN` configured in the server's `.env` file.

### Step 3: Run the Agent

Double-click `PrintEaseAgent.exe`.

- The agent automatically detects the default printer configured in Windows.
- It begins polling your hosted PrintEase server for pending print jobs.
- When an order is received, it downloads the PDF, sends it to the printer with the user's selected print options (copies, color, duplex, orientation), and reports the status back to the server.

---

## 🔄 Run Automatically on Windows Startup

To ensure printing continues seamlessly even if the printer computer restarts:

1. Press <kbd>Win</kbd> + <kbd>R</kbd> to open the **Run** dialog.
2. Type `shell:startup` and press **Enter** (this opens your user's Startup folder).
3. Right-click inside the folder, select **New > Shortcut**.
4. Browse and select `PrintEaseAgent.exe` from your client directory.
5. Click **Next** and **Finish**.

Now, whenever the printer PC turns on or reboots, the PrintEase agent will launch automatically in the background.

---

## 🎛 Managing Printing via Admin Dashboard

Printer operators and administrators can control the entire printing process through the web dashboard without interacting with the physical computer:

1. Log in to `/admin/dashboard` using your admin credentials.
2. In the top header, inspect the **Print Agent** status widget:
   - 🟢 **Receiving jobs - Agent online (Printer Name)**: The agent is connected and actively processing the queue.
   - 🟡 **Started - waiting for agent**: The queue is enabled, waiting for the agent to poll.
   - 🔴 **Stopped - Agent offline / online**: Printing is paused or the agent is disconnected.
3. Use the toggle button to manage operation:
   - Click **"Stop receiving jobs"** to temporarily pause dispatching (e.g., when refilling paper, changing toner, or taking a break).
   - Click **"Start receiving jobs"** to resume dispatching pending orders.
4. From the dashboard table, you can also:
   - Monitor live printing progress (`pending` → `printing` → `completed`).
   - Retry failed print jobs with a single click.
   - View/download uploaded PDFs.
   - Mark orders as delivered (which securely deletes the PDF from server disk).

---

## 📂 Project Structure

```
printease/
├── authentication/             # JWT authentication & Argon2 password hashing
├── models/                     # SQLAlchemy models and database connection
├── printer_pc/
│   └── dist/                   # Standalone printer client files
│       ├── PrintEaseAgent.exe  # Compiled single-file Windows print agent
│       ├── agent_config.json   # Server URL and agent authentication token
│       └── agent_config.example.json # Reference configuration template
├── routers/
│   ├── admin.py                # Admin dashboard & printer pause/resume endpoints
│   ├── agent.py                # Agent polling, file retrieval & result APIs
│   ├── orders.py               # Order creation & upload endpoints
│   ├── payments.py             # Razorpay checkout & webhook handlers
│   └── users.py                # User registration & profile management
├── schemas/                    # Pydantic validation schemas
├── services/
│   ├── payment_service.py      # Razorpay payment verification & refunds
│   └── print_dispatcher.py     # Print queue dispatcher & timeout reaper
├── static/                     # CSS, JavaScript & icons
├── templates/                  # Jinja2 HTML templates (Admin dashboard, user portal)
├── utils/                      # Rate limiter, cost calculators, validators
├── config.py                   # Pydantic application settings
├── create_admin.py             # CLI script to bootstrap admin users
├── docker-compose.yml          # Production Docker Compose orchestration
├── Dockerfile                  # FastAPI application Docker container
└── requirements.txt            # Python server dependencies
```
