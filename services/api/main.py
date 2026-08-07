import hashlib
import os
import uuid
from contextlib import contextmanager
from datetime import date
from pathlib import Path

import psycopg
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field, field_validator

from worker import convert_file

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://dicom:change-me@postgres:5432/dicomflow")
ORGANIZATION_ID = uuid.UUID(os.getenv("DEFAULT_ORGANIZATION_ID", "00000000-0000-4000-8000-000000000001"))
storage = Path(os.getenv("STORAGE_PATH", "/data/uploads"))
storage.mkdir(parents=True, exist_ok=True)
allowed = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".txt", ".csv", ".pdf", ".dcm"}

SEX_CODES = {1: "Hombre", 2: "Mujer", 3: "Intersexual", 93: "No informado", 99: "Desconocido"}
GENDER_CODES = {1: "Masculino", 2: "Femenina", 3: "Transgénero masculino", 4: "Transgénero femenina", 5: "No binarie", 6: "Otra", 7: "No revelado"}
CIVIL_STATUS_CODES = {1: "Soltero(a)", 2: "Casado(a)", 3: "Viudo(a)", 4: "Divorciado(a)", 5: "Separado(a) judicialmente", 6: "Conviviente civil", 99: "Desconocido"}
INSURANCE_CODES = {1: "FONASA", 2: "ISAPRE", 3: "CAPREDENA", 4: "DIPRECA", 5: "SISA", 96: "Ninguna", 99: "Desconocido"}
EDUCATION_CODES = {1: "Preescolar", 2: "Especial o diferencial", 3: "Básica o primaria", 4: "Media o secundaria", 5: "Educación superior", 6: "Sin instrucción", 97: "No recuerda", 98: "No responde"}
REGION_CODES = {1: "Tarapacá", 2: "Antofagasta", 3: "Atacama", 4: "Coquimbo", 5: "Valparaíso", 6: "O’Higgins", 7: "Maule", 8: "Biobío", 9: "La Araucanía", 10: "Los Lagos", 11: "Aysén", 12: "Magallanes", 13: "Metropolitana de Santiago", 14: "Los Ríos", 15: "Arica y Parinacota", 16: "Ñuble", 99: "Desconocido"}

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
    second_family_name: str | None = Field(default=None, max_length=120)
    social_name: str | None = Field(default=None, max_length=120)
    identifier_type: str = "RUT"
    identifier_value: str = Field(min_length=1, max_length=80)
    birth_date: date
    sex_biological_code: int = 99
    gender_code: int = 7
    civil_status_code: int = 99
    insurance_code: int = 99
    education_code: int = 98
    last_grade: int = Field(default=0, ge=0, le=8)
    nationality_code: str = Field(default="152", pattern=r"^\d{3}$")
    nationality_label: str = Field(default="Chile", max_length=100)
    origin_country_code: str = Field(default="152", pattern=r"^\d{3}$")
    origin_country_label: str = Field(default="Chile", max_length=100)
    region_code: int = 99
    commune_code: str | None = Field(default=None, max_length=10)
    commune_label: str | None = Field(default=None, max_length=120)
    street_name: str | None = Field(default=None, max_length=180)
    street_number: str | None = Field(default=None, max_length=30)
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

    @field_validator("birth_date")
    @classmethod
    def valid_birth_date(cls, value: date):
        if value > date.today():
            raise ValueError("La fecha de nacimiento no puede ser futura")
        return value

    @field_validator("sex_biological_code")
    @classmethod
    def valid_sex_code(cls, value: int):
        if value not in SEX_CODES:
            raise ValueError("Código de sexo biológico no permitido por EIS")
        return value

    @field_validator("gender_code")
    @classmethod
    def valid_gender_code(cls, value: int):
        if value not in GENDER_CODES:
            raise ValueError("Código de identidad de género no permitido por EIS")
        return value

    @field_validator("civil_status_code")
    @classmethod
    def valid_civil_status(cls, value: int):
        if value not in CIVIL_STATUS_CODES:
            raise ValueError("Código de estado civil no permitido por EIS")
        return value

    @field_validator("insurance_code")
    @classmethod
    def valid_insurance(cls, value: int):
        if value not in INSURANCE_CODES:
            raise ValueError("Código de previsión no permitido por EIS")
        return value

    @field_validator("education_code")
    @classmethod
    def valid_education(cls, value: int):
        if value not in EDUCATION_CODES:
            raise ValueError("Código de nivel de instrucción no permitido por EIS")
        return value

    @field_validator("region_code")
    @classmethod
    def valid_region(cls, value: int):
        if value not in REGION_CODES:
            raise ValueError("Código de región no permitido por EIS")
        return value

    @field_validator("phone")
    @classmethod
    def valid_phone(cls, value: str | None):
        if not value:
            return None
        normalized = "".join(character for character in value if character.isdigit())
        if len(normalized) != 9 or not (normalized.startswith("9") or normalized[0] in "23456"):
            raise ValueError("El teléfono debe contener 9 dígitos según EIS")
        return normalized


def build_cmbd(payload: PatientCreate, identifier_value: str):
    identification = {
        "Nombres": payload.given_names.strip(),
        "PrimerApellido": payload.family_names.strip(),
        "SegundoApellido": (payload.second_family_name or "").strip() or None,
        "NombreSocial": (payload.social_name or "").strip() or None,
    }
    if payload.identifier_type == "RUT":
        run, verifier = identifier_value.split("-")
        identification.update({"Run": int(run), "DigitoVerificador": verifier})
    else:
        identification["OtraIdentificacion"] = identifier_value
    return {
        "norma": "MINSAL-DEIS-EIS",
        "fuente": "https://deis.minsal.cl/norma-tecnica-de-estandares-de-informacion-en-salud-eis/",
        "identificacionPersona": identification,
        "datosDemograficos": {
            "FechaNacimiento": payload.birth_date.strftime("%d-%m-%Y"),
            "SexobiologicoCodigo": payload.sex_biological_code,
            "SexobiologicoGlosa": SEX_CODES[payload.sex_biological_code],
            "GeneroCodigo": payload.gender_code,
            "GeneroGlosa": GENDER_CODES[payload.gender_code],
            "NacionalidadCodigo": payload.nationality_code,
            "NacionalidadGlosa": payload.nationality_label.strip(),
            "PaisOrigenCodigo": payload.origin_country_code,
            "PaisOrigenGlosa": payload.origin_country_label.strip(),
        },
        "situacionPersona": {
            "EstadoCivilCodigo": payload.civil_status_code,
            "EstadoCivilGlosa": CIVIL_STATUS_CODES[payload.civil_status_code],
        },
        "nivelInstruccion": {
            "NivelInstruccionCodigo": payload.education_code,
            "NivelInstruccionGlosa": EDUCATION_CODES[payload.education_code],
            "UltimoCursoAprobado": payload.last_grade,
        },
        "prevision": {
            "PrevisionCodigo": payload.insurance_code,
            "PrevisionGlosa": INSURANCE_CODES[payload.insurance_code],
        },
        "contacto": {"TelefonoMovil": payload.phone, "CorreoElectronico": payload.email},
        "ubicacionDireccion": {
            "RegionCodigo": payload.region_code,
            "RegionGlosa": REGION_CODES[payload.region_code],
            "ComunaCodigo": payload.commune_code,
            "ComunaGlosa": payload.commune_label,
            "NombreVia": payload.street_name,
            "NumeroDomicilio": payload.street_number,
        },
    }


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
                   identifier_type, identifier_value, email, phone, cmbd, created_at
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
    cmbd = build_cmbd(payload, identifier_value)
    family_names = " ".join(
        value for value in [payload.family_names.strip(), (payload.second_family_name or "").strip()] if value
    )
    with database() as connection:
        ensure_organization(connection)
        try:
            patient = connection.execute(
                """
                INSERT INTO patients (organization_id, given_names, family_names, birth_date, sex,
                    identifier_type, identifier_value, rut_normalized, email, phone, cmbd)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, given_names, family_names, birth_date, sex,
                          identifier_type, identifier_value, email, phone, cmbd, created_at
                """,
                (ORGANIZATION_ID, payload.given_names.strip(), family_names,
                 payload.birth_date, SEX_CODES[payload.sex_biological_code], payload.identifier_type,
                 identifier_value, rut_normalized, payload.email or None, payload.phone, Jsonb(cmbd)),
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
