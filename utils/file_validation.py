import asyncio
import os
import uuid
import pypdf
from fastapi import UploadFile

# Custom Exceptions
class FileSizeExceededError(Exception): pass
class InvalidFormatError(Exception): pass
class PDFProcessingError(Exception): pass

async def validate_and_count_pdf(file: UploadFile, max_size_mb: int = 20) -> int:
    # Convert the MB limit to Bytes for an accurate comparison
    max_size_bytes = max_size_mb * 1024 * 1024

    if file.size and file.size > max_size_bytes:
        raise FileSizeExceededError(f"File size exceeds the {max_size_mb} MB limit")

    if file.content_type != "application/pdf":
        raise InvalidFormatError("Only PDF files are allowed")

    try:
        reader = await asyncio.to_thread(pypdf.PdfReader, file.file)

        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:
                raise PDFProcessingError("Password-protected PDFs are not allowed")

        page_count = len(reader.pages)

        await file.seek(0)
        return page_count

    except pypdf.errors.PdfReadError:
        raise PDFProcessingError("Corrupted or invalid PDF")
    except Exception as e:
        raise PDFProcessingError("Unable to process PDF")


def generate_secure_filename(original_filename: str) -> str:
    _, extension = os.path.splitext(original_filename)
    safe_extension = extension.lower() if extension else ".pdf"

    unique_name = uuid.uuid4().hex

    return f"{unique_name}{safe_extension}"



