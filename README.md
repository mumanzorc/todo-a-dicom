# Todo a DICOM / DICOM Flow

Plataforma clínica y documental para convertir JPG, PNG, TIFF, BMP, TXT, CSV y DICOM; operar cargas individuales o por lote; organizar pacientes y estudios; visualizar DICOM; auditar acciones; generar reportes y gestionar documentos y relaciones (CRM).

## Inicio con Docker Compose

1. Copiar `.env.example` a `.env` y reemplazar contraseñas y secretos.
2. Ejecutar `docker compose up -d --build`.
3. Abrir `http://localhost:8866`. Desde otro equipo de la red, usar la IP del servidor, por ejemplo `http://192.168.31.147:8866`. En producción, el proxy TLS publica el dominio configurado y reenvía al puerto 8866.

El contenedor web se llama `todo_a_dicom`, publica el puerto 8866 y tiene `restart: unless-stopped`. La API se mantiene dentro de la red privada de Compose y la aplicación web actúa como proxy. API y workers no tienen nombre fijo, por lo que se pueden escalar con `docker compose up -d --scale api=3 --scale worker=5`.

Para reconstruir una actualización sin eliminar los datos persistentes:

```bash
docker compose down
docker compose build --no-cache
docker compose up -d
docker compose ps
```

## Primera fase funcional

- Resumen con métricas reales obtenidas desde PostgreSQL.
- Registro y búsqueda de pacientes con validación de RUT.
- Soporte para pasaporte, documento extranjero, identificador interno y otros identificadores.
- Carga múltiple de JPG, PNG, TIFF, BMP, TXT, CSV, PDF y DICOM.
- Creación persistente de lotes y conversiones.
- Procesamiento asíncrono mediante Celery y Redis.
- Seguimiento automático de estados: en cola, procesando, disponible o fallida.
- Comunicación web–API a través de un proxy interno, sin publicar directamente el puerto 8000.

Los módulos Exámenes, Visor DICOM, Documentos, CRM, Reportes y Auditoría se muestran como próxima fase y no presentan acciones simuladas.

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

Este repositorio entrega un MVP funcional para registrar pacientes, cargar archivos y seguir conversiones. La autenticación, edición y archivo de pacientes, estudios completos, envío SMTP, integración OHIF, antivirus, descarga ZIP con streaming, documentos, CRM, auditoría y reportes firmados corresponden a fases posteriores. Consultar `SECURITY.md` antes de usar datos reales.
