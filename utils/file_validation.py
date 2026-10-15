import asyncio
import uuid
import pypdf
from fastapi import UploadFile
from config import settings


# Custom Exceptions
class FileSizeExceededError(Exception):
    pass


class InvalidFormatError(Exception):
    pass


class PDFProcessingError(Exception):
    pass


async def validate_and_count_pdf(file: UploadFile, max_size_mb: int = 20) -> int:
    # Convert the MB limit to Bytes for an accurate comparison
    max_size_bytes = max_size_mb * 1024 * 1024

    if file.size and file.size > max_size_bytes:
        raise FileSizeExceededError(f"File size exceeds the {max_size_mb} MB limit")

    if file.content_type != "application/pdf":
        raise InvalidFormatError("Only PDF files are allowed")

    try:

        def inspect_pdf():
            # Enforce the actual spooled size, even when client metadata is absent.
            file.file.seek(0, 2)
            if file.file.tell() > max_size_bytes:
                raise FileSizeExceededError(f"File size exceeds the {max_size_mb} MB limit")
            file.file.seek(0)
            if file.file.read(5) != b"%PDF-":
                raise PDFProcessingError("Invalid PDF header")
            file.file.seek(0)
            reader = pypdf.PdfReader(file.file)
            if reader.is_encrypted:
                raise PDFProcessingError("Password-protected PDFs are not allowed")
            count = len(reader.pages)
            if not 1 <= count <= settings.max_pdf_pages:
                raise PDFProcessingError(f"PDF must contain 1 to {settings.max_pdf_pages} pages")
            return count

        page_count = await asyncio.to_thread(inspect_pdf)

        await file.seek(0)
        return page_count

    except (FileSizeExceededError, PDFProcessingError):
        raise
    except pypdf.errors.PdfReadError:
        raise PDFProcessingError("Corrupted or invalid PDF")
    except Exception:
        raise PDFProcessingError("Unable to process PDF")


def generate_secure_filename(original_filename: str) -> str:
    unique_name = uuid.uuid4().hex
    return f"{unique_name}.pdf"
