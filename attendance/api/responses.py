"""HTTP response helpers; kept out of ``services`` so the desktop never needs FastAPI."""
import io

from fastapi.responses import StreamingResponse
from openpyxl import Workbook


def streaming_excel_response(
    wb: Workbook,
    filename: str,
) -> StreamingResponse:
    """Envuelve un Workbook en StreamingResponse para FastAPI."""
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
