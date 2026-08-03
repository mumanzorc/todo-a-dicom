import os, uuid
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from worker import convert_file

app = FastAPI(title="DICOM Flow API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=[os.getenv("WEBHOOK_URL", "https://example.com")], allow_methods=["*"], allow_headers=["*"])
storage = Path(os.getenv("STORAGE_PATH", "/data/uploads")); storage.mkdir(parents=True, exist_ok=True)
allowed = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".txt", ".csv", ".pdf", ".dcm"}

@app.get("/health")
def health(): return {"status": "ok", "service": "dicom-flow-api"}

@app.post("/v1/conversions", status_code=202)
async def create_conversion(files: list[UploadFile] = File(...), patient_id: str | None = None):
    if not files: raise HTTPException(400, "Debe adjuntar al menos un archivo")
    batch_id, jobs = str(uuid.uuid4()), []
    for upload in files:
        suffix = Path(upload.filename or "").suffix.lower()
        if suffix not in allowed: raise HTTPException(415, f"Formato no soportado: {suffix}")
        target = storage / f"{uuid.uuid4()}{suffix}"
        target.write_bytes(await upload.read())
        task = convert_file.delay(str(target), patient_id, batch_id, upload.filename)
        jobs.append({"job_id": task.id, "filename": upload.filename})
    return {"batch_id": batch_id, "jobs": jobs, "status": "queued"}
