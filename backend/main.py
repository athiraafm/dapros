from __future__ import annotations

from pathlib import Path
import uuid
import json
import pandas as pd
from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from processing import create_dapros, filter_ncli, get_witel_preview, pembagian_data

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

app = FastAPI(title="DAPROS API", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

LAST_OUTPUTS: dict[str, Path] = {}

MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB


@app.exception_handler(413)
async def request_entity_too_large(request: Request, exc):
    return JSONResponse(status_code=413, content={"detail": "File terlalu besar. Maksimum ukuran upload adalah 100 MB."})


def save_upload(file: UploadFile, prefix: str) -> Path:
    ext = Path(file.filename or "file.xlsx").suffix or ".xlsx"
    path = UPLOAD_DIR / f"{prefix}_{uuid.uuid4().hex}{ext}"
    size = 0
    with path.open("wb") as buffer:
        while chunk := file.file.read(1024 * 1024):  # baca per 1 MB
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413,
                    detail="File terlalu besar. Maksimum ukuran upload adalah 100 MB."
                )
            buffer.write(chunk)
    return path


def register_output(path: Path) -> str:
    file_id = uuid.uuid4().hex
    LAST_OUTPUTS[file_id] = path
    return file_id


@app.get("/")
def root():
    return {"status": "ok", "message": "DAPROS FastAPI aktif"}


@app.post("/api/create-dapros")
def api_create_dapros(file: UploadFile = File(...)):
    try:
        input_path = save_upload(file, "create")
        output_path = OUTPUT_DIR / f"hasil_rekomendasi_offering_{uuid.uuid4().hex}.xlsx"
        summary = create_dapros(input_path, output_path)
        file_id = register_output(output_path)
        return {"success": True, "file_id": file_id, "filename": "hasil_rekomendasi_offering.xlsx", "summary": summary}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/filter-ncli")
def api_filter_ncli(dapros_file: UploadFile = File(...), historis_files: list[UploadFile] = File(...)):
    try:
        dapros_path = save_upload(dapros_file, "dapros")
        hist_paths = [save_upload(f, "historis") for f in historis_files]
        output_path = OUTPUT_DIR / f"Dapros_Clean_Tanpa_VAM_{uuid.uuid4().hex}.xlsx"
        summary = filter_ncli(dapros_path, hist_paths, output_path)
        file_id = register_output(output_path)
        return {"success": True, "file_id": file_id, "filename": "Dapros_Clean_Tanpa_VAM.xlsx", "summary": summary}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/debug-file")
def api_debug_file(file: UploadFile = File(...)):
    """Debug endpoint: kembalikan daftar sheet dan jumlah baris dari file yang diupload."""
    try:
        input_path = save_upload(file, "debug")
        xls = pd.ExcelFile(input_path)
        sheets_info = []
        for sheet in xls.sheet_names:
            df = pd.read_excel(input_path, sheet_name=sheet, dtype=str, nrows=None)
            cols = df.columns.astype(str).str.strip().tolist()
            sheets_info.append({
                "sheet": sheet,
                "rows": int(len(df)),
                "columns": cols[:15]  # max 15 kolom
            })
        return {"success": True, "sheets": sheets_info}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/pembagian-preview")
def api_pembagian_preview(file: UploadFile = File(...)):
    try:
        input_path = save_upload(file, "preview")
        # Ambil info sheet untuk debug
        xls = pd.ExcelFile(input_path)
        sheets_info = [{"sheet": s, "rows": int(len(pd.read_excel(input_path, sheet_name=s, dtype=str)))} for s in xls.sheet_names]
        summary = get_witel_preview(input_path)
        summary["sheets_info"] = sheets_info
        # simpan path agar bisa dipakai proses setelah preview
        file_id = register_output(input_path)
        return {"success": True, "upload_id": file_id, "summary": summary}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/pembagian-data")
def api_pembagian_data(file: UploadFile = File(None), upload_id: str = Form(None), allocations: str = Form(...)):
    try:
        if upload_id and upload_id in LAST_OUTPUTS:
            input_path = LAST_OUTPUTS[upload_id]
        elif file is not None:
            input_path = save_upload(file, "pembagian")
        else:
            raise ValueError("File pembagian belum dikirim.")
        output_path = OUTPUT_DIR / f"hasil_pembagian_{uuid.uuid4().hex}.zip"
        summary = pembagian_data(input_path, json.loads(allocations), output_path)
        file_id = register_output(output_path)
        return {"success": True, "file_id": file_id, "filename": "hasil_pembagian_dapros.zip", "summary": summary}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/download/{file_id}")
def download(file_id: str):
    path = LAST_OUTPUTS.get(file_id)
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="File output tidak ditemukan.")
    media_type = "application/zip" if path.suffix.lower() == ".zip" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return FileResponse(path, filename=path.name, media_type=media_type)
