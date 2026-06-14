import time
import subprocess
from pathlib import Path
import win32print

from config import PRINTER_NAME

def wait_for_print_queue(printer_name: str):
    """Block until the Windows print spooler queue is empty."""
    time.sleep(1)
    hprinter = win32print.OpenPrinter(printer_name)
    try:
        while True:
            jobs = win32print.EnumJobs(hprinter, 0, -1, 2)
            if not jobs:
                break
            print(f"[INFO] Waiting... {len(jobs)} job(s) in '{printer_name}' queue.")
            time.sleep(2)
    finally:
        win32print.ClosePrinter(hprinter)


def print_pdf(file_path: Path, options: dict) -> bool:
    """Send a (stamped) PDF to SumatraPDF and wait for the physical print."""
    print(f"\n[INFO] Starting print job: {file_path.name}")

    raw_copies  = options.get("copies", 1)
    copies      = int(raw_copies) if str(raw_copies).isdigit() else 1
    
    raw_color   = options.get("color_mode", "bw")
    color_mode  = "monochrome" if raw_color == "bw" else "color"
    
    raw_side    = options.get("side_mode", "single")
    side_mode   = "duplex" if raw_side == "double" else "simplex"
    
    orientation = options.get("orientation", "portrait")
    paper_size  = options.get("paper_size", "A4")

    print(f"[INFO] {copies} copies | {color_mode} | {side_mode} | {orientation} | {paper_size}")

    print_target = file_path
    if copies > 1:
        from pypdf import PdfReader, PdfWriter
        reader = PdfReader(str(file_path))
        writer = PdfWriter()
        
        doc_pages = list(reader.pages)
        if side_mode == "duplex" and len(doc_pages) % 2 != 0:
            last_page = doc_pages[-1]
            blank_page = writer.add_blank_page(width=last_page.mediabox.width, height=last_page.mediabox.height)
            doc_pages.append(blank_page)
            
        for _ in range(copies):
            for page in doc_pages:
                writer.add_page(page)
                
        multi_copy_path = file_path.parent / (file_path.stem + f"_{copies}x.pdf")
        with open(multi_copy_path, "wb") as f:
            writer.write(f)
        print_target = multi_copy_path
        print(f"[INFO] Generated N-copy document: {multi_copy_path.name}")

    settings = f"{color_mode},{side_mode},{orientation},paper={paper_size}"
    command  = [
        "SumatraPDF.exe",
        "-print-to",       PRINTER_NAME,
        "-print-settings", settings,
        "-exit-on-print",
        str(print_target),
    ]

    try:
        print(f"[INFO] Running: {' '.join(command)}")
        subprocess.run(command, check=True, capture_output=True, text=True)
        print(f"[INFO] Handed off to Windows. Waiting for queue...")
        wait_for_print_queue(PRINTER_NAME)
        
        if copies > 1 and print_target.exists():
            try:
                print_target.unlink()
            except Exception as e:
                print(f"[ERROR] Could not delete temp copy file: {e}")
                
        print("[SUCCESS] Queue empty - print complete.\n")
        return True

    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Print failed (code {e.returncode}): {e.stderr}")
        return False
    except FileNotFoundError:
        print("[ERROR] SumatraPDF.exe not found.")
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        return False
