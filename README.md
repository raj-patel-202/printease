# PrintEase

PrintEase is a modern, web-based remote printing service. Users can upload PDF documents, customize print settings (number of copies, color/B&W, single/double sided, paper size), pay online securely via Razorpay, and have their documents automatically dispatched to a physical printer connected to a remote Windows machine.

---

## Project Structure

All backend server components, configuration files, and the Windows printer client (`printer-pc/`) sit side-by-side at the root of the repository:

```
printease/
├── authentication/       # User & admin auth, password hashing, JWT sessions
├── models/               # SQLAlchemy async database models
├── resource/             # Uploaded PDF files & storage directories
├── routers/              # FastAPI API routes (pages, auth, orders, agent, admin)
├── schemas/              # Pydantic validation schemas & request/response models
├── services/             # Business logic (payments, printing, pricing, dispatcher)
├── static/               # Frontend CSS, JavaScript, and asset files
├── templates/            # Jinja2 HTML templates
├── utils/                # Utility functions, rate limiting, and helpers
├── printer-pc/           # Client application for the machine connected to the printer
│   ├── PrintEaseAgent.exe   # Pre-compiled Windows background agent
│   └── agent_config.json   # Connection settings (server URL & agent token)
├── .dockerignore         # Docker build ignore rules
├── .env.example          # Environment variables template
├── .gitignore            # Git ignore rules
├── Dockerfile            # Container image definition for the web backend
├── docker-compose.yml    # Multi-container orchestration (FastAPI + PostgreSQL)
├── config.py             # Pydantic application configuration & settings
├── create_admin.py       # Interactive CLI script to create an admin user
├── main.py               # FastAPI application entrypoint & lifecycle handlers
├── requirements.txt      # Python dependencies
└── README.md
```

---

## 1. Environment Configuration (`.env`) — The Most Crucial Step

Setting up the `.env` file correctly is **mandatory** before starting the application. PrintEase uses Pydantic Settings, which validates required keys during application startup. If any required key is missing or invalid, the server will fail to start.

### Step 1.1: Create your `.env` file

Copy the included template into a new `.env` file in the root directory:

```bash
# On Linux / macOS / Git Bash
cp .env.example .env

# On Windows PowerShell
copy .env.example .env
```

### Step 1.2: Generate Secure Secret Keys

PrintEase requires cryptographically secure random keys for `SECRET_KEY` and `AGENT_TOKEN`. You can generate them instantly using any of the following commands:

**Using Python (Recommended - Cross Platform):**
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

**Using OpenSSL:**
```bash
openssl rand -hex 32
```

**Using Windows PowerShell:**
```powershell
[Convert]::ToHexString((1..32 | ForEach-Object { Get-Random -Maximum 256 }))
```

> **Tip:** Run the command twice — once for `SECRET_KEY` and once for `AGENT_TOKEN`.

---

### Detailed Variable Breakdown

Here is what each environment variable does, how to obtain it, why it is required, and what breaks if it is missing:

| Variable | Required | Default / Example | Purpose & Source |
| :--- | :---: | :--- | :--- |
| `SECRET_KEY` | **Yes** | *64-character hex string* | **JWT Token Signing:** Cryptographically signs and verifies login and admin session cookies. Generated using `python -c "import secrets; print(secrets.token_hex(32))"`. |
| `COOKIE_SECURE` | **Yes** | `False` (Dev) / `True` (Prod) | **Cookie Security Flag:** When `True`, cookies are only transmitted over HTTPS. Must be `False` for local HTTP development. |
| `POSTGRES_USER` | **Yes** | `printeaseadmin` | **PostgreSQL Username:** Used by Docker Compose to create the database user and by the backend to connect. |
| `POSTGRES_PASSWORD` | **Yes** | *Your secure DB password* | **PostgreSQL Password:** Database authentication password. |
| `POSTGRES_DB` | **Yes** | `printease` | **PostgreSQL Database Name:** Database instance name created in PostgreSQL. |
| `DATABASE_URL` | **Yes** | `postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}` | **Async Database Connection URI:** Used by SQLAlchemy and asyncpg to connect to the database. (If running without Docker, change `@db:5432` to `@localhost:5432`). |
| `RAZORPAY_API_KEY` | **Yes** | `rzp_test_...` | **Public Razorpay Key:** Sent to the frontend checkout page to display the Razorpay payment modal. |
| `RAZORPAY_API_SECRET` | **Yes** | *Razorpay Secret String* | **Private Razorpay Secret:** Used by the backend to create orders and verify payment signatures (`HMAC-SHA256`). |
| `RAZORPAY_WEBHOOK_SECRET` | **Yes** | *Custom Webhook Secret* | **Razorpay Webhook Secret:** Validates asynchronous webhook callbacks from Razorpay. |
| `CURRENCY` | No | `INR` | **Transaction Currency:** Currency code passed to Razorpay (e.g., `INR`). Defaults to `INR`. |
| `WEB3FORMS_ACCESS_KEY` | **Yes** | *Web3Forms UUID* | **Contact Form Email Forwarder:** Forwards contact form messages to your email without needing an SMTP mail server. |
| `AGENT_TOKEN` | **Yes** | *64-character hex string* | **Printer Agent Shared Secret:** Secret bearer token shared between the server and `printer-pc/agent_config.json`. |

---

### In-Depth: Role, How to Obtain, and Consequences of Misconfiguration

#### 1. `SECRET_KEY`
- **Role:** Secures all user and admin sessions. PrintEase signs JSON Web Tokens (JWT) using HMAC-SHA256 with this key to store access tokens in browser cookies.
- **How to get:** Generate a 32-byte (64 hex characters) random string using:
  ```bash
  python -c "import secrets; print(secrets.token_hex(32))"
  ```
- **Why it is needed:** Prevents session hijacking and cookie tampering.
- **What happens if not set properly:** The application will fail startup validation. If set to a weak, predictable, or publicly known string, attackers can forge admin session tokens and gain full administrative access without credentials.

#### 2. `COOKIE_SECURE`
- **Role:** Instructs web browsers whether to only transmit session cookies over encrypted HTTPS connections (`Secure` flag).
- **How to set:**
  - Set to `False` when running locally on `http://localhost:8000`.
  - Set to `True` when running in production with an SSL/TLS certificate (`https://`).
- **Why it is needed:** Enforces HTTPS in production while allowing local testing.
- **What happens if not set properly:** If you set this to `True` while testing on `http://localhost`, modern browsers will silently reject the cookie. Users and admins will be unable to log in because the session cookie is discarded instantly.

#### 3. `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, & `DATABASE_URL`
- **Role:** Configures the database container credentials and the connection string used by FastAPI via SQLAlchemy's async engine (`asyncpg`).
- **How to get:** Define your preferred username, password, and database name. In `docker-compose.yml`, the `db` service automatically initializes PostgreSQL using these credentials.
- **Why it is needed:** The database stores user accounts, print orders, payment logs, document metadata, and printer status records.
- **What happens if not set properly:** FastAPI cannot connect to PostgreSQL. The server will throw connection errors on startup, and no users, orders, or files can be created or queried.

#### 4. `RAZORPAY_API_KEY`, `RAZORPAY_API_SECRET`, & `RAZORPAY_WEBHOOK_SECRET`
- **Role:**
  - `RAZORPAY_API_KEY`: Injected into the checkout page template (`checkout.html`) to initialize the Razorpay checkout popup.
  - `RAZORPAY_API_SECRET`: Kept private on the server to create Razorpay payment orders via the Razorpay REST API and verify HMAC-SHA256 signatures after payment completion.
  - `RAZORPAY_WEBHOOK_SECRET`: Verifies authenticity of background webhook events sent by Razorpay to `/api/payments/webhook`.
- **How to get:**
  1. Register or log in to the [Razorpay Dashboard](https://dashboard.razorpay.com).
  2. Switch to **Test Mode** (for development) or **Live Mode** (for production).
  3. Navigate to **Account & Settings > API Keys > Generate Key**. Copy the Key ID (`RAZORPAY_API_KEY`) and Key Secret (`RAZORPAY_API_SECRET`).
  4. (Optional for webhooks) Go to **Account & Settings > Webhooks > Add New Webhook**. Set your webhook URL (e.g., `https://your-domain.com/api/payments/webhook`), select payment events, and enter a secret key (`RAZORPAY_WEBHOOK_SECRET`).
- **Why it is needed:** Enables customers to pay online before documents are sent to the printer.
- **What happens if not set properly:**
  - Missing API Key: The "Pay Now" button fails, and the Razorpay popup will not appear.
  - Invalid API Secret: Order creation or cryptographic signature verification fails on the server; the order is never confirmed as paid, and the document is never dispatched to the printer.

#### 5. `WEB3FORMS_ACCESS_KEY`
- **Role:** Handles contact form submissions directly from the frontend (`contact.html`) to deliver inquiries to your email inbox without configuring an SMTP mail server.
- **How to get:**
  1. Visit [Web3Forms](https://web3forms.com).
  2. Enter your email address and click **Create Access Key**.
  3. Check your email for your free access key UUID and paste it here.
- **Why it is needed:** Connects the contact form on the website to your inbox.
- **What happens if not set properly:** Inquiries submitted through the Contact Us page will fail with an error, preventing customers from contacting support.

#### 6. `AGENT_TOKEN`
- **Role:** Shared authentication secret between the central PrintEase server and the remote Windows printer client (`printer-pc/PrintEaseAgent.exe`).
- **How to get:** Generate a secure random string (e.g. using `python -c "import secrets; print(secrets.token_hex(32))"`). Put this value in `.env` as `AGENT_TOKEN` **and** in `printer-pc/agent_config.json` as `"agent_token"`.
- **Why it is needed:** The printer agent polls the server's `/api/agent/` endpoints to retrieve pending jobs, download documents, and report printer health. The server verifies the `Authorization: Bearer <AGENT_TOKEN>` header on every request.
- **What happens if not set properly:** If `AGENT_TOKEN` is missing, or does not match `agent_config.json`, the printer agent will receive `401 Unauthorized` errors. The admin dashboard will show the printer as permanently **Offline**, and **no documents will ever be printed**.

---

## 2. Server Setup & Running

### Option A: Running with Docker (Recommended)

Make sure Docker and Docker Compose are installed and running on your machine:

1. **Build and start containers:**
   ```bash
   docker compose up --build -d
   ```
   The web application will be available at: **`http://localhost:8000`**

2. **Create an Admin Account:**
   ```bash
   docker compose exec web python create_admin.py
   ```
   Follow the interactive prompt to enter an admin email and password.

3. **Check server logs (optional):**
   ```bash
   docker compose logs -f web
   ```

4. **Stop the server:**
   ```bash
   docker compose down
   ```

---

### Option B: Running Locally (Without Docker)

If running without Docker, ensure Python 3.11+ and PostgreSQL are installed locally:

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure `.env` for local PostgreSQL:**
   Ensure `DATABASE_URL` in `.env` points to your local database host (e.g., `localhost` instead of `db`):
   ```env
   DATABASE_URL=postgresql+asyncpg://printeaseadmin:your_postgres_password@localhost:5432/printease
   ```

3. **Run the server:**
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```

4. **Create an Admin Account:**
   ```bash
   python create_admin.py
   ```

---

## 3. Printer PC Setup (`printer-pc/`)

This step is done on the Windows computer physically connected (via USB or LAN) to the printer.

### Files inside `printer-pc/`:
- `PrintEaseAgent.exe`: Pre-compiled background agent that receives print jobs from the server and prints them.
- `agent_config.json`: Client configuration file.

### How to Configure and Run:

1. **Configure `agent_config.json`:**
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
