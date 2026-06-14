import json
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

from config import INCOMING_DIR
from services.pdf_stamper import stamp_pdf
from services.print_service import print_pdf

app = FastAPI(title="Printer Agent")

@app.get("/api/health")
async def health_check():
    return {"status": "ok"}

@app.post("/api/print")
async def print_job(
    file:    UploadFile = File(...),
    options: str        = Form(...),
):
    if not INCOMING_DIR.exists():
        INCOMING_DIR.mkdir(parents=True)

    try:
        options_dict = json.loads(options)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in options")

    file_path = INCOMING_DIR / file.filename
    with open(file_path, "wb") as f:
        f.write(await file.read())
    print(f"[INFO] Saved {file.filename} -> {file_path}")

    order_id   = options_dict.get("order_id", "N/A")
    print_date = datetime.now().strftime("%d/%m/%Y")
    stamped_path = None

    try:
        stamped_path = stamp_pdf(file_path, order_id, print_date)
        print_target = stamped_path
    except Exception as e:
        print(f"[WARNING] Stamping failed: {e} - printing original.")
        print_target = file_path

    success = print_pdf(print_target, options_dict)

    for p in [file_path, stamped_path]:
        if p and p.exists():
            try:
                p.unlink()
                print(f"[INFO] Deleted {p.name}")
            except Exception as e:
                print(f"[ERROR] Could not delete {p}: {e}")

    if success:
        return JSONResponse(status_code=200, content={"message": "Printed successfully"})
    raise HTTPException(status_code=500, detail="Failed to print document")

if __name__ == "__main__":
    print("=" * 44)
    print("      PRINTER PC FASTAPI AGENT")
    print("=" * 44)
    uvicorn.run(app, host="0.0.0.0", port=8001)
