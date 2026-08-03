# Todo a DICOM / DICOM Flow

Plataforma clínica y documental para convertir JPG, PNG, TIFF, BMP, TXT, CSV y DICOM; operar cargas individuales o por lote; organizar pacientes y estudios; visualizar DICOM; auditar acciones; generar reportes y gestionar documentos y relaciones (CRM).

## Inicio local

1. Copiar `.env.example` a `.env` y reemplazar contraseñas y secretos.
2. Ejecutar `docker compose up -d --build`.
3. Abrir `http://localhost:8866`. En producción, el proxy TLS publica `https://example.com` y reenvía al puerto 8866.

El servicio web solicitado se llama `todo_a_dicom`, publica el puerto 8866 y tiene `restart: unless-stopped`. API y workers no tienen nombre fijo, por lo que se pueden escalar con `docker compose up -d --scale api=3 --scale worker=5`.

## Arquitectura

- Web responsive: dashboard operativo y navegación de módulos.
- API FastAPI: recepción validada y cargas por lote.
- Celery + Redis: conversiones asíncronas, reintentos y escalado horizontal.
- PostgreSQL: usuarios, restablecimiento de contraseña, pacientes, CMBD, estudios, documentos, CRM y auditoría.
- Orthanc: archivo/servidor DICOM y base para integrar OHIF Viewer.
- Volúmenes persistentes: base de datos, originales/DICOM, Redis y Orthanc.

## Identidad del paciente

Se admiten RUT chileno (normalizado y validado por módulo 11), pasaporte, documento nacional extranjero, identificador interno y otro identificador. Los pacientes sin RUT reciben un identificador interno y pueden reconciliarse posteriormente conservando la trazabilidad.

## Versiones en GitHub

La estrategia es SemVer (`v1.2.3`). Al publicar un tag, GitHub Actions construye y sube la imagen a GitHub Container Registry. Ejemplo: `git tag -a v0.1.0 -m "MVP"` y `git push origin v0.1.0`.

## Alcance actual y ruta a producción

Este repositorio entrega un MVP ejecutable y una interfaz demostrable. Los contratos y el esquema están preparados para CRUD de usuarios/pacientes/archivos, recuperación por email, estudios, CMBD, auditoría, documentos y CRM. Las pantallas completas, endpoints restantes, envío SMTP, integración OHIF, antivirus, descarga ZIP con streaming y reportes firmados corresponden a la siguiente fase. Consultar `SECURITY.md` antes de usar datos reales.
