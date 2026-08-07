import hashlib
import os
import uuid
from contextlib import contextmanager
from pathlib import Path

import psycopg
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from psycopg.rows import dict_row
from pydantic import BaseModel, Field, field_validator

from worker import convert_file

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://dicom:change-me@postgres:5432/dicomflow")
ORGANIZATION_ID = uuid.UUID(os.getenv("DEFAULT_ORGANIZATION_ID", "00000000-0000-4000-8000-000000000001"))
storage = Path(os.getenv("STORAGE_PATH", "/data/uploads"))
storage.mkdir(parents=True, exist_ok=True)
allowed = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".txt", ".csv", ".pdf", ".dcm"}

app = FastAPI(title="DICOM Flow API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("WEB_ORIGIN", "http://localhost:8866")],
    allow_methods=["*"],
    allow_headers=["*"],
)


@contextmanager
def database():
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        yield connection


def ensure_organization(connection):
    connection.execute(
        "INSERT INTO organizations (id, name) VALUES (%s, %s) ON CONFLICT (id) DO NOTHING",
        (ORGANIZATION_ID, os.getenv("ORGANIZATION_NAME", "Clínica Central")),
    )


@app.on_event("startup")
def prepare_database():
    with database() as connection:
        connection.execute(
            "ALTER TABLE conversions ADD COLUMN IF NOT EXISTS patient_id uuid REFERENCES patients(id)"
        )
        ensure_organization(connection)


def normalize_rut(value: str) -> str:
    normalized = value.upper().replace(".", "").replace("-", "").strip()
    if len(normalized) < 2 or not normalized[:-1].isdigit():
        raise ValueError("RUT inválido")
    body, verifier = normalized[:-1], normalized[-1]
    total, factor = 0, 2
    for digit in reversed(body):
        total += int(digit) * factor
        factor = 2 if factor == 7 else factor + 1
    expected_value = 11 - (total % 11)
    expected = "0" if expected_value == 11 else "K" if expected_value == 10 else str(expected_value)
    if verifier != expected:
        raise ValueError("Dígito verificador del RUT inválido")
    return f"{int(body)}-{verifier}"


class PatientCreate(BaseModel):
    given_names: str = Field(min_length=1, max_length=120)
    family_names: str = Field(min_length=1, max_length=120)
    identifier_type: str = "RUT"
    identifier_value: str = Field(min_length=1, max_length=80)
    birth_date: str | None = None
    sex: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=40)

    @field_validator("identifier_type")
    @classmethod
    def valid_identifier_type(cls, value: str):
        value = value.upper()
        if value not in {"RUT", "PASSPORT", "NATIONAL_ID", "INTERNAL", "OTHER"}:
            raise ValueError("Tipo de identificador no soportado")
        return value

    @field_validator("identifier_value")
    @classmethod
    def clean_identifier(cls, value: str):
        return value.strip()


@app.get("/health")
def health():
    with database() as connection:
        connection.execute("SELECT 1").fetchone()
    return {"status": "ok", "service": "dicom-flow-api"}


@app.get("/v1/patients")
def list_patients(search: str = Query(default="", max_length=120)):
    pattern = f"%{search.strip()}%"
    with database() as connection:
        ensure_organization(connection)
        rows = connection.execute(
            """
            SELECT id, given_names, family_names, birth_date, sex,
                   identifier_type, identifier_value, email, phone, created_at
            FROM patients
            WHERE organization_id = %s AND archived_at IS NULL
              AND (%s = '%%' OR CONCAT_WS(' ', given_names, family_names, identifier_value, email) ILIKE %s)
            ORDER BY created_at DESC LIMIT 200
            """,
            (ORGANIZATION_ID, pattern, pattern),
        ).fetchall()
    return {"patients": rows}


@app.post("/v1/patients", status_code=201)
def create_patient(payload: PatientCreate):
    rut_normalized = None
    identifier_value = payload.identifier_value
    if payload.identifier_type == "RUT":
        try:
            rut_normalized = normalize_rut(identifier_value)
            identifier_value = rut_normalized
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
    with database() as connection:
        ensure_organization(connection)
        try:
            patient = connection.execute(
                """
                INSERT INTO patients (organization_id, given_names, family_names, birth_date, sex,
                    identifier_type, identifier_value, rut_normalized, email, phone)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, given_names, family_names, birth_date, sex,
                          identifier_type, identifier_value, email, phone, created_at
                """,
                (ORGANIZATION_ID, payload.given_names.strip(), payload.family_names.strip(),
                 payload.birth_date or None, payload.sex or None, payload.identifier_type,
                 identifier_value, rut_normalized, payload.email or None, payload.phone or None),
            ).fetchone()
        except psycopg.errors.UniqueViolation as error:
            raise HTTPException(409, "Ya existe un paciente con ese identificador") from error
    return patient


@app.post("/v1/conversions", status_code=202)
async def create_conversion(files: list[UploadFile] = File(...), patient_id: str | None = Form(default=None)):
    if not files:
        raise HTTPException(400, "Debe adjuntar al menos un archivo")
    try:
        patient_uuid = uuid.UUID(patient_id) if patient_id else None
    except ValueError as error:
        raise HTTPException(422, "Identificador de paciente inválido") from error
    batch_id, jobs, queued_tasks = uuid.uuid4(), [], []
    with database() as connection:
        if patient_uuid and not connection.execute(
            "SELECT 1 FROM patients WHERE id = %s AND archived_at IS NULL", (patient_uuid,)
        ).fetchone():
            raise HTTPException(404, "Paciente no encontrado")
        for upload in files:
            suffix = Path(upload.filename or "").suffix.lower()
            if suffix not in allowed:
                raise HTTPException(415, f"Formato no soportado: {suffix or 'sin extensión'}")
            content = await upload.read()
            if not content:
                raise HTTPException(400, f"El archivo {upload.filename} está vacío")
            target = storage / f"{uuid.uuid4()}{suffix}"
            target.write_bytes(content)
            conversion_id = uuid.uuid4()
            connection.execute(
                """
                INSERT INTO conversions (id, batch_id, patient_id, original_name, original_mime,
                    source_sha256, source_path, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'QUEUED')
                """,
                (conversion_id, batch_id, patient_uuid, upload.filename or target.name, upload.content_type,
                 hashlib.sha256(content).hexdigest(), str(target)),
            )
            queued_tasks.append((conversion_id, target, upload.filename))
    for conversion_id, target, original_name in queued_tasks:
        try:
            task = convert_file.delay(
                str(target), str(patient_uuid) if patient_uuid else None,
                str(batch_id), original_name, str(conversion_id)
            )
        except Exception as error:
            with database() as connection:
                connection.execute(
                    "UPDATE conversions SET status = 'FAILED', error_message = %s, completed_at = now() WHERE id = %s",
                    ("No se pudo enviar el trabajo al worker", conversion_id),
                )
            raise HTTPException(503, "No se pudo enviar la conversión al worker") from error
        jobs.append({"conversion_id": conversion_id, "job_id": task.id, "filename": original_name})
    return {"batch_id": batch_id, "jobs": jobs, "status": "QUEUED"}


@app.get("/v1/conversions")
def list_conversions(limit: int = Query(default=50, ge=1, le=200)):
    with database() as connection:
        rows = connection.execute(
            """SELECT c.id, c.batch_id, c.patient_id, c.original_name, c.original_mime,
                      c.status, c.error_message, c.created_at, c.completed_at,
                      CONCAT_WS(' ', p.given_names, p.family_names) AS patient_name
                 FROM conversions c LEFT JOIN patients p ON p.id = c.patient_id
                ORDER BY c.created_at DESC LIMIT %s""",
            (limit,),
        ).fetchall()
    return {"conversions": rows}


@app.get("/v1/conversions/batches/{batch_id}")
def get_conversion_batch(batch_id: uuid.UUID):
    with database() as connection:
        rows = connection.execute(
            """SELECT id, batch_id, original_name, status, error_message, dicom_path,
                      created_at, completed_at FROM conversions WHERE batch_id = %s ORDER BY created_at""",
            (batch_id,),
        ).fetchall()
    if not rows:
        raise HTTPException(404, "Lote no encontrado")
    return {"batch_id": batch_id, "conversions": rows}


@app.get("/v1/dashboard")
def dashboard():
    with database() as connection:
        ensure_organization(connection)
        patients = connection.execute(
            "SELECT COUNT(*) AS total FROM patients WHERE organization_id = %s AND archived_at IS NULL",
            (ORGANIZATION_ID,),
        ).fetchone()["total"]
        counts = connection.execute(
            """SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE status = 'READY') AS ready,
                      COUNT(*) FILTER (WHERE status IN ('QUEUED', 'PROCESSING')) AS processing,
                      COUNT(*) FILTER (WHERE status = 'FAILED') AS failed FROM conversions"""
        ).fetchone()
    return {"patients": patients, **counts}
