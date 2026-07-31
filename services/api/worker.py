import csv, os, uuid
from pathlib import Path
from celery import Celery
from PIL import Image, ImageDraw
import pydicom
from pydicom.dataset import Dataset, FileDataset
from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage, generate_uid

celery = Celery("dicomflow", broker=os.getenv("REDIS_URL", "redis://redis:6379/0"), backend=os.getenv("REDIS_URL", "redis://redis:6379/0"))

def rasterize(path: Path) -> Image.Image:
    if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}: return Image.open(path).convert("L")
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() == ".csv": text = "\n".join(" | ".join(row) for row in csv.reader(text.splitlines()))
    lines = text.splitlines()[:120] or ["Documento vacío"]
    image = Image.new("L", (1600, max(1000, 40 * len(lines) + 100)), "white")
    draw = ImageDraw.Draw(image)
    for i, line in enumerate(lines): draw.text((50, 50 + i * 40), line[:180], fill="black")
    return image

@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def convert_file(self, source: str, patient_id: str | None, batch_id: str, original_name: str | None):
    path = Path(source)
    if path.suffix.lower() == ".dcm": return {"status": "ready", "path": str(path)}
    image = rasterize(path); pixels = image.tobytes()
    meta = Dataset(); meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage; meta.MediaStorageSOPInstanceUID = generate_uid(); meta.TransferSyntaxUID = ExplicitVRLittleEndian
    out = path.with_suffix(".dcm"); ds = FileDataset(str(out), {}, file_meta=meta, preamble=b"\0" * 128)
    ds.SOPClassUID = meta.MediaStorageSOPClassUID; ds.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
    ds.PatientID = patient_id or f"ANON-{uuid.uuid4().hex[:10].upper()}"; ds.PatientName = "ANONIMO"
    ds.StudyInstanceUID = generate_uid(); ds.SeriesInstanceUID = generate_uid(); ds.Modality = "OT"
    ds.StudyDescription = original_name or path.name; ds.Rows = image.height; ds.Columns = image.width
    ds.SamplesPerPixel = 1; ds.PhotometricInterpretation = "MONOCHROME2"; ds.BitsAllocated = 8; ds.BitsStored = 8; ds.HighBit = 7; ds.PixelRepresentation = 0; ds.PixelData = pixels
    ds.save_as(out, enforce_file_format=True)
    return {"status": "ready", "path": str(out), "batch_id": batch_id}
