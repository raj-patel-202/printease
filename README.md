# PrintEase (Smart Printing Service)

PrintEase is a modern, web-based remote printing solution built with FastAPI. It allows users to securely upload documents, configure print settings (copies, color, paper size), process payments via Razorpay, and automatically route the jobs to a remotely connected physical printer.

## 🏗 Architecture Overview

The repository is deliberately divided into two distinct components:

1. **The Server (Web Backend):** The entirety of this repository (**excluding** the `printer_pc` directory) acts as the central server. It handles user authentication, file uploads, secure checkout (Razorpay), database management (PostgreSQL), and the API that orchestrates the print queue.
2. **The Printer Client (`printer_pc/`):** **IMPORTANT:** This directory contains the client code meant to be executed on the physical, remote Windows machine directly connected to the printer. This directory operates independently and must be kept logically and physically separate from the main server deployment.

## ✨ Features

- **User Authentication:** Secure registration and login using Argon2 password hashing and JWT cookies.
- **File Upload & Validation:** Secure PDF uploads with strict file size, page counting, and format validation.
- **Dynamic Cost Calculation:** Calculates print costs based on page count, color mode (B&W/Color), side mode (single/double-sided), and applies automated discounts.
- **Payment Integration:** Integrated with Razorpay for secure checkout and refunds.
- **Admin Dashboard:** Administrative controls for monitoring the print queue, retrying failed jobs, marking deliveries, and pausing/resuming the print dispatcher.
- **Print Dispatcher:** Automatically dispatches queued, paid jobs to the remote `printer_pc` client for physical printing.

## 🚀 Getting Started (Server)

### Prerequisites
- Docker and Docker Compose
- Python 3.13 (for local development)

### Environment Setup

Create a `.env` file in the root directory and add the necessary configuration:

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
PRINTER_PC_TAILSCALE_URL=http://your_tailscale_ip:8001
```

### Running with Docker

The easiest way to run the server is using Docker Compose. This will spin up both the FastAPI application and the PostgreSQL database.

```bash
docker-compose up --build -d
```
The server will be accessible at `http://localhost:8000`.

### Creating an Admin Profile

To access the admin dashboard, you need an administrative account. Run the `create_admin.py` script provided in the repository to generate one:

```bash
# If running locally
python create_admin.py

# If running via Docker
docker exec -it printease_web python create_admin.py
```
You will be prompted to enter an admin email and a secure password.

## 🖨 Setting up the Printer Client (`printer_pc`)

> **Note:** The `printer_pc` folder must be moved to the Windows computer directly connected to your physical printer.

Navigate to the `printer_pc` directory on the target machine and set up the environment:

```bash
cd printer_pc
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Run the printer client script:
```bash
python main.py
```

### Secure Communication via Tailscale

To ensure that print jobs and metadata are transferred securely between your central server and the remote Printer PC, it is highly recommended to use **Tailscale** to create a secure, encrypted peer-to-peer network.

1. Install [Tailscale](https://tailscale.com/) on both the server and the Windows Printer PC.
2. Authenticate both devices onto the same Tailnet.
3. Retrieve the Tailscale IP address of the Printer PC.
4. Set the `PRINTER_PC_TAILSCALE_URL` environment variable on your server to point to the Printer PC's Tailscale IP and port (e.g., `http://100.x.y.z:8001`). 

This guarantees that the printer's API is not exposed to the public internet, and all traffic remains encrypted.

## 📂 Project Structure

- `authentication/` - JWT auth and password hashing.
- `models/` - SQLAlchemy database models.
- `routers/` - FastAPI endpoints grouped by domain (users, orders, payments, admin).
- `schemas/` - Pydantic schemas for request/response validation.
- `services/` - Core business logic and payment integrations.
- `static/` & `templates/` - Frontend assets and Jinja2 templates.
- `utils/` - Helper functions, rate limiting, validators, and queue management.
- `printer_pc/` - The remote client to be deployed on the printer-connected PC.
