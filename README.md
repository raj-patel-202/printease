# PrintEase

PrintEase is a simple web-based remote printing service. Users can upload PDF documents, choose print settings (copies, color/B&W, single/double sided, paper size), pay online via Razorpay, and their documents are automatically sent to a remote printer.

The project is organized into two main folders:
1. `server/` – The web application backend, database, and admin dashboard.
2. `printer-pc/` – The lightweight client app that runs on the computer connected to the printer.

---

## Project Structure

```
printease/
├── server/           # Central backend (FastAPI, PostgreSQL, Admin Web UI)
│   ├── authentication/
│   ├── models/
│   ├── resource/
│   ├── routers/
│   ├── schemas/
│   ├── services/
│   ├── static/
│   ├── templates/
│   ├── utils/
│   ├── config.py
│   ├── create_admin.py
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── requirements.txt
│   └── main.py
│
├── printer-pc/       # Client application for the printer machine
│   ├── PrintEaseAgent.exe          # Pre-compiled executable (ready to run)
│   ├── agent_config.json          # Configuration file (server URL & token)
│   └── agent_config.example.json  # Example configuration template
│
└── README.md
```

---

## 1. Printer PC Setup (`printer-pc/`)

This runs on the Windows computer physically connected to the printer. **No Python installation or command-line knowledge is required.**

### Files inside `printer-pc/`:
- `PrintEaseAgent.exe`: Standalone program that listens for print jobs and sends them to your printer.
- `agent_config.json`: Config file pointing to your hosted server.

### How to use:

1. **Configure the connection:**
   Open `agent_config.json` in Notepad:
   ```json
   {
     "server_url": "http://localhost:8000",
     "agent_token": "your_agent_token"
   }
   ```
   - `server_url`: The address of your running PrintEase server (e.g., `http://localhost:8000` or your hosted domain).
   - `agent_token`: Secret token that matches `AGENT_TOKEN` in `server/.env`.

2. **Run the program:**
   - Double-click `PrintEaseAgent.exe`.
   - It will start and appear as an icon in your **Windows System Tray** (bottom-right corner, near the clock).

3. **Select your printer:**
   - Right-click the PrintEase icon in the System Tray.
   - Click **Select Printer** and choose your printer from the list of installed Windows printers.
   - The app will now automatically poll the server for pending jobs and print them as they arrive.

4. **(Optional) Run automatically on Windows startup:**
   If you want the program to start whenever the PC boots up:
   - Press `Win + R`, type `shell:startup`, and press Enter.
   - Create a shortcut to `PrintEaseAgent.exe` inside that folder.

---

## 2. Server Setup (`server/`)

The server handles user logins, file uploads, payments, and manages the print queue.

### Requirements:
- Docker & Docker Compose (easiest way to run)
- Or Python 3.13 for manual running

### Configuration:

Create a `.env` file inside the `server/` folder:

```env
SECRET_KEY=your_secret_key
COOKIE_SECURE=False

POSTGRES_USER=printeaseadmin
POSTGRES_PASSWORD=your_postgres_password
POSTGRES_DB=printease
DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}

RAZORPAY_API_KEY=your_razorpay_key
RAZORPAY_API_SECRET=your_razorpay_secret
RAZORPAY_WEBHOOK_SECRET=your_razorpay_webhook_secret

WEB3FORMS_ACCESS_KEY=your_web3forms_key
CURRENCY=INR

# Token used by printer-pc to connect
AGENT_TOKEN=your_agent_token
```

### Running the server with Docker:

```bash
cd server
docker compose up --build -d
```
The website will be available at `http://localhost:8000`.

### Creating an Admin account:

To access the admin dashboard:

```bash
# If running with Docker
docker compose exec web python create_admin.py

# If running locally
python create_admin.py
```
Enter an email and password when prompted.

---

## 3. Admin Dashboard & Print Control

Admins can manage the entire printing process through the web browser at `http://localhost:8000/admin/dashboard`:

- **Printer Status:** Shows whether the printer agent is currently online or offline, and which printer is selected in the system tray.
- **Start / Stop Receiving Jobs:**
  - Click **Stop receiving jobs** to pause sending prints (e.g., when refilling paper or toner).
  - Click **Start receiving jobs** to resume printing.
- **Manage Orders:** View live print status, retry failed jobs, preview PDFs, and mark completed jobs as delivered (which deletes the file from disk).
