import csv
import os
import uuid
from pathlib import Path

import psycopg
from celery import Celery
from PIL import Image, ImageDraw
from pydicom.dataset import Dataset, FileDataset
from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage, generate_uid

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://dicom:change-me@postgres:5432/dicomflow")
celery = Celery(
    "dicomflow",
    broker=os.getenv("REDIS_URL", "redis://redis:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://redis:6379/0"),
)


def update_conversion(conversion_id: str, status: str, **fields):
    assignments = ["status = %s"]
    values = [status]
    for name in ("dicom_path", "error_message"):
        if name in fields:
            assignments.append(f"{name} = %s")
            values.append(fields[name])
    if status in {"READY", "FAILED"}:
        assignments.append("completed_at = now()")
    values.append(conversion_id)
    with psycopg.connect(DATABASE_URL) as connection:
        connection.execute(
            f"UPDATE conversions SET {', '.join(assignments)} WHERE id = %s", values
        )


def rasterize(path: Path) -> Image.Image:
    if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}:
        return Image.open(path).convert("L")
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() == ".csv":
        text = "\n".join(" | ".join(row) for row in csv.reader(text.splitlines()))
    lines = text.splitlines()[:120] or ["Documento vacío"]
    image = Image.new("L", (1600, max(1000, 40 * len(lines) + 100)), "white")
    draw = ImageDraw.Draw(image)
    for index, line in enumerate(lines):
        draw.text((50, 50 + index * 40), line[:180], fill="black")
    return image


@celery.task(bind=True, max_retries=3)
def convert_file(
    self,
    source: str,
    patient_id: str | None,
    batch_id: str,
    original_name: str | None,
    conversion_id: str,
):
    update_conversion(conversion_id, "PROCESSING")
    try:
        path = Path(source)
        if path.suffix.lower() == ".dcm":
            update_conversion(conversion_id, "READY", dicom_path=str(path))
            return {"status": "READY", "path": str(path), "batch_id": batch_id}

        image = rasterize(path)
        meta = Dataset()
        meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
        meta.MediaStorageSOPInstanceUID = generate_uid()
        meta.TransferSyntaxUID = ExplicitVRLittleEndian
        output = path.with_suffix(".dcm")
        dataset = FileDataset(str(output), {}, file_meta=meta, preamble=b"\0" * 128)
        dataset.SOPClassUID = meta.MediaStorageSOPClassUID
        dataset.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
        dataset.PatientID = patient_id or f"ANON-{uuid.uuid4().hex[:10].upper()}"
        dataset.PatientName = "ANONIMO"
        dataset.StudyInstanceUID = generate_uid()
        dataset.SeriesInstanceUID = generate_uid()
        dataset.Modality = "OT"
        dataset.StudyDescription = original_name or path.name
        dataset.Rows = image.height
        dataset.Columns = image.width
        dataset.SamplesPerPixel = 1
        dataset.PhotometricInterpretation = "MONOCHROME2"
        dataset.BitsAllocated = 8
        dataset.BitsStored = 8
        dataset.HighBit = 7
        dataset.PixelRepresentation = 0
        dataset.PixelData = image.tobytes()
        dataset.save_as(output, enforce_file_format=True)
        update_conversion(conversion_id, "READY", dicom_path=str(output))
        return {"status": "READY", "path": str(output), "batch_id": batch_id}
    except Exception as error:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=error, countdown=2 ** (self.request.retries + 1))
        update_conversion(conversion_id, "FAILED", error_message=str(error)[:1000])
        raise
