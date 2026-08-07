"use client";

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

type Patient = {
  id: string;
  given_names: string;
  family_names: string;
  identifier_type: string;
  identifier_value: string;
  birth_date?: string;
  email?: string;
  phone?: string;
  created_at: string;
};

type Conversion = {
  id: string;
  batch_id: string;
  patient_id?: string;
  patient_name?: string;
  original_name: string;
  status: "QUEUED" | "PROCESSING" | "READY" | "REVIEW" | "FAILED";
  error_message?: string;
  created_at: string;
};

type Dashboard = { patients: number; total: number; ready: number; processing: number; failed: number };
type ActiveModule = "Resumen" | "Pacientes" | "Conversión" | "Próxima fase";

const futureModules = ["Exámenes", "Visor DICOM", "Documentos", "CRM", "Reportes", "Auditoría"];
const statusLabels: Record<Conversion["status"], string> = {
  QUEUED: "En cola",
  PROCESSING: "Procesando",
  READY: "Disponible",
  REVIEW: "Revisión",
  FAILED: "Fallida",
};

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api/backend/${path}`, { ...options, cache: "no-store" });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(payload.detail)
      ? payload.detail.map((item: { msg?: string }) => item.msg).filter(Boolean).join(". ")
      : payload.detail;
    throw new Error(detail || "No fue posible completar la operación");
  }
  return payload as T;
}

function formatDate(value?: string) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("es-CL", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export default function Home() {
  const [active, setActive] = useState<ActiveModule>("Resumen");
  const [futureTitle, setFutureTitle] = useState("");
  const [patients, setPatients] = useState<Patient[]>([]);
  const [conversions, setConversions] = useState<Conversion[]>([]);
  const [dashboard, setDashboard] = useState<Dashboard>({ patients: 0, total: 0, ready: 0, processing: 0, failed: 0 });
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState<{ kind: "success" | "error"; text: string } | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);

  const notify = useCallback((text: string, kind: "success" | "error" = "success") => {
    setNotice({ kind, text });
    window.setTimeout(() => setNotice(null), 4200);
  }, []);

  const loadData = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true);
    try {
      const [patientData, conversionData, dashboardData] = await Promise.all([
        api<{ patients: Patient[] }>("v1/patients"),
        api<{ conversions: Conversion[] }>("v1/conversions?limit=50"),
        api<Dashboard>("v1/dashboard"),
      ]);
      setPatients(patientData.patients);
      setConversions(conversionData.conversions);
      setDashboard(dashboardData);
    } catch (error) {
      notify(error instanceof Error ? error.message : "No se pudo conectar con la API", "error");
    } finally {
      if (!quiet) setLoading(false);
    }
  }, [notify]);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadData(), 0);
    return () => window.clearTimeout(timer);
  }, [loadData]);
  useEffect(() => {
    if (!dashboard.processing) return;
    const timer = window.setInterval(() => void loadData(true), 4000);
    return () => window.clearInterval(timer);
  }, [dashboard.processing, loadData]);

  const navigate = (module: ActiveModule, title?: string) => {
    setActive(module);
    setFutureTitle(title ?? "");
  };

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand"><span className="brandmark">D</span><div><strong>DICOM Flow</strong><small>Clínica Central</small></div></div>
        <nav aria-label="Navegación principal">
          {(["Resumen", "Pacientes", "Conversión"] as ActiveModule[]).map((item) => (
            <button key={item} className={active === item ? "active" : ""} onClick={() => navigate(item)}>
              <span aria-hidden="true">{item === "Resumen" ? "⌂" : item === "Pacientes" ? "♙" : "⇄"}</span>{item}
              {item === "Conversión" && dashboard.processing > 0 && <b>{dashboard.processing}</b>}
            </button>
          ))}
          {futureModules.map((item) => (
            <button key={item} className={active === "Próxima fase" && futureTitle === item ? "active" : ""} onClick={() => navigate("Próxima fase", item)}>
              <span aria-hidden="true">◇</span>{item}<small>Próxima</small>
            </button>
          ))}
        </nav>
        <div className="serviceState"><i className={loading ? "pending" : ""}/><div><strong>{loading ? "Sincronizando" : "Servicios conectados"}</strong><small>API, PostgreSQL y workers</small></div></div>
      </aside>

      <section className="workspace">
        <header>
          <div><p className="eyebrow">CENTRO DE OPERACIONES</p><h1>{active === "Próxima fase" ? futureTitle : active}</h1><p>Gestión clínica y conversión documental en tiempo real</p></div>
          <div className="headerActions">
            {active === "Pacientes" && <button className="secondary" onClick={() => searchRef.current?.focus()}>Buscar paciente</button>}
            <button className="primary" onClick={() => navigate("Conversión")}>＋ Nueva conversión</button>
          </div>
        </header>

        {loading ? <LoadingState /> : (
          <>
            {active === "Resumen" && <Summary dashboard={dashboard} conversions={conversions} navigate={navigate} />}
            {active === "Pacientes" && <Patients patients={patients} searchRef={searchRef} onCreated={() => loadData()} notify={notify} />}
            {active === "Conversión" && <Conversions patients={patients} conversions={conversions} onSubmitted={() => loadData()} notify={notify} />}
            {active === "Próxima fase" && <FutureModule title={futureTitle} navigate={navigate} />}
          </>
        )}
        <footer><span><i/> Datos persistentes en PostgreSQL</span><span>Actualización automática durante conversiones</span></footer>
      </section>
      {notice && <div role="status" className={`toast ${notice.kind}`}>{notice.kind === "success" ? "✓" : "!"} {notice.text}</div>}
    </main>
  );
}

function LoadingState() {
  return <div className="loadingPanel"><span className="spinner"/><strong>Cargando información clínica…</strong></div>;
}

function Summary({ dashboard, conversions, navigate }: { dashboard: Dashboard; conversions: Conversion[]; navigate: (module: ActiveModule) => void }) {
  const cards = [
    ["Pacientes registrados", dashboard.patients, "♙", "blue"],
    ["Conversiones listas", dashboard.ready, "✓", "green"],
    ["En procesamiento", dashboard.processing, "↻", "orange"],
    ["Con errores", dashboard.failed, "!", "red"],
  ];
  return <>
    <div className="stats">{cards.map(([label, value, icon, color]) => <article key={String(label)}><div className={`statIcon ${color}`}>{icon}</div><div><span>{label}</span><strong>{value}</strong><p>Datos actuales del sistema</p></div></article>)}</div>
    <div className="dashboardGrid">
      <article className="panel recent">
        <div className="panelHead"><div><h2>Conversiones recientes</h2><p>Estado real de los últimos archivos</p></div><button className="textButton" onClick={() => navigate("Conversión")}>Ver conversiones</button></div>
        <ConversionTable conversions={conversions.slice(0, 8)} />
      </article>
      <article className="panel quick">
        <div className="panelHead"><div><h2>Acciones disponibles</h2><p>Primera fase funcional</p></div></div>
        <button onClick={() => navigate("Conversión")}><span className="quickIcon">⇧</span><div><strong>Convertir archivos</strong><small>JPG, PNG, TIFF, TXT, CSV, PDF o DICOM</small></div><b>›</b></button>
        <button onClick={() => navigate("Pacientes")}><span className="quickIcon green">♙</span><div><strong>Registrar paciente</strong><small>RUT, pasaporte u otro identificador</small></div><b>›</b></button>
      </article>
    </div>
  </>;
}

function Patients({ patients, searchRef, onCreated, notify }: { patients: Patient[]; searchRef: React.RefObject<HTMLInputElement | null>; onCreated: () => Promise<void>; notify: (text: string, kind?: "success" | "error") => void }) {
  const [query, setQuery] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const filtered = useMemo(() => patients.filter((patient) =>
    `${patient.given_names} ${patient.family_names} ${patient.identifier_value} ${patient.email ?? ""}`.toLowerCase().includes(query.toLowerCase())
  ), [patients, query]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    const form = new FormData(event.currentTarget);
    const payload = Object.fromEntries(form.entries());
    try {
      await api<Patient>("v1/patients", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(payload) });
      event.currentTarget.reset();
      setShowForm(false);
      notify("Paciente registrado correctamente");
      await onCreated();
    } catch (error) {
      notify(error instanceof Error ? error.message : "No se pudo registrar el paciente", "error");
    } finally { setSaving(false); }
  }

  return <div className="moduleGrid">
    <article className="panel listPanel">
      <div className="panelHead"><div><h2>Pacientes</h2><p>{patients.length} registros activos</p></div><button className="primary small" onClick={() => setShowForm((value) => !value)}>{showForm ? "Cerrar" : "＋ Registrar paciente"}</button></div>
      <div className="toolbar"><label>⌕<input ref={searchRef} value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Nombre, RUT o correo"/></label></div>
      {filtered.length ? <div className="tableWrap"><table><thead><tr><th>Paciente</th><th>Identificador</th><th>Contacto</th><th>Registro</th></tr></thead><tbody>{filtered.map((patient) => <tr key={patient.id}><td><div className="identity"><span className="patientDot">{patient.given_names[0]}{patient.family_names[0]}</span><div><strong>{patient.given_names} {patient.family_names}</strong><small>{patient.id.slice(0, 8)}</small></div></div></td><td><strong>{patient.identifier_value}</strong><small>{patient.identifier_type}</small></td><td>{patient.email || patient.phone || "Sin contacto"}</td><td>{formatDate(patient.created_at)}</td></tr>)}</tbody></table></div> : <EmptyState title="No hay pacientes que coincidan" text="Ajusta la búsqueda o registra un paciente nuevo."/>}
    </article>
    {showForm && <article className="panel formPanel"><div className="panelHead"><div><h2>Nuevo paciente</h2><p>Los campos marcados son obligatorios</p></div></div><form onSubmit={submit}>
      <div className="formGrid"><label>Nombres *<input name="given_names" required maxLength={120}/></label><label>Apellidos *<input name="family_names" required maxLength={120}/></label><label>Tipo de identificación *<select name="identifier_type" defaultValue="RUT"><option value="RUT">RUT</option><option value="PASSPORT">Pasaporte</option><option value="NATIONAL_ID">Documento extranjero</option><option value="INTERNAL">Identificador interno</option><option value="OTHER">Otro</option></select></label><label>Número de identificación *<input name="identifier_value" required maxLength={80}/></label><label>Fecha de nacimiento<input name="birth_date" type="date"/></label><label>Sexo<select name="sex" defaultValue=""><option value="">Sin especificar</option><option>Femenino</option><option>Masculino</option><option>Otro</option></select></label><label>Correo<input name="email" type="email" maxLength={254}/></label><label>Teléfono<input name="phone" maxLength={40}/></label></div>
      <div className="formActions"><button type="button" className="secondary" onClick={() => setShowForm(false)}>Cancelar</button><button className="primary" disabled={saving}>{saving ? "Guardando…" : "Guardar paciente"}</button></div>
    </form></article>}
  </div>;
}

function Conversions({ patients, conversions, onSubmitted, notify }: { patients: Patient[]; conversions: Conversion[]; onSubmitted: () => Promise<void>; notify: (text: string, kind?: "success" | "error") => void }) {
  const [files, setFiles] = useState<File[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!files.length) return notify("Selecciona al menos un archivo", "error");
    setSubmitting(true);
    const source = new FormData(event.currentTarget);
    const payload = new FormData();
    const patientId = source.get("patient_id");
    if (patientId) payload.append("patient_id", String(patientId));
    files.forEach((file) => payload.append("files", file));
    try {
      const result = await api<{ batch_id: string }>("v1/conversions", { method: "POST", body: payload });
      setFiles([]);
      if (inputRef.current) inputRef.current.value = "";
      notify(`Lote ${result.batch_id.slice(0, 8)} enviado a procesamiento`);
      await onSubmitted();
    } catch (error) {
      notify(error instanceof Error ? error.message : "No se pudo iniciar la conversión", "error");
    } finally { setSubmitting(false); }
  }

  return <div className="conversionLayout">
    <article className="panel uploadPanel"><div className="panelHead"><div><h2>Nueva conversión</h2><p>Los archivos se almacenan y procesan en segundo plano</p></div></div><form onSubmit={submit}>
      <label className="fieldLabel">Paciente asociado<select name="patient_id" defaultValue=""><option value="">Paciente anónimo</option>{patients.map((patient) => <option key={patient.id} value={patient.id}>{patient.given_names} {patient.family_names} · {patient.identifier_value}</option>)}</select></label>
      <button type="button" className="dropZone" onClick={() => inputRef.current?.click()}><span>⇧</span><strong>Seleccionar archivos</strong><small>JPG, PNG, TIFF, BMP, TXT, CSV, PDF o DICOM</small></button>
      <input ref={inputRef} className="srOnly" type="file" multiple accept=".jpg,.jpeg,.png,.bmp,.tif,.tiff,.txt,.csv,.pdf,.dcm" onChange={(event) => setFiles(Array.from(event.target.files ?? []))}/>
      {files.length > 0 && <ul className="fileList">{files.map((file) => <li key={`${file.name}-${file.size}`}><span>{file.name}</span><small>{(file.size / 1024).toFixed(1)} KB</small></li>)}</ul>}
      <button className="primary wide" disabled={submitting || !files.length}>{submitting ? "Enviando…" : `Convertir ${files.length || ""} archivo${files.length === 1 ? "" : "s"}`}</button>
    </form></article>
    <article className="panel historyPanel"><div className="panelHead"><div><h2>Historial de conversiones</h2><p>Se actualiza automáticamente mientras existen trabajos activos</p></div></div><ConversionTable conversions={conversions}/></article>
  </div>;
}

function ConversionTable({ conversions }: { conversions: Conversion[] }) {
  if (!conversions.length) return <EmptyState title="Aún no hay conversiones" text="Carga el primer archivo para iniciar el flujo."/>;
  return <div className="tableWrap"><table><thead><tr><th>Archivo</th><th>Paciente</th><th>Estado</th><th>Fecha</th></tr></thead><tbody>{conversions.map((conversion) => <tr key={conversion.id}><td><strong>{conversion.original_name}</strong><small>Lote {conversion.batch_id.slice(0, 8)}</small></td><td>{conversion.patient_name || "Anónimo"}</td><td><span className={`status ${conversion.status.toLowerCase()}`}>● {statusLabels[conversion.status]}</span>{conversion.error_message && <small className="errorText">{conversion.error_message}</small>}</td><td>{formatDate(conversion.created_at)}</td></tr>)}</tbody></table></div>;
}

function EmptyState({ title, text }: { title: string; text: string }) {
  return <div className="emptyState"><span>◇</span><strong>{title}</strong><p>{text}</p></div>;
}

function FutureModule({ title, navigate }: { title: string; navigate: (module: ActiveModule) => void }) {
  return <article className="panel future"><span>◇</span><p className="eyebrow">PRÓXIMA FASE</p><h2>{title}</h2><p>Este módulo todavía no forma parte de la primera fase funcional. Pacientes, conversiones y seguimiento ya están disponibles.</p><button className="primary" onClick={() => navigate("Resumen")}>Volver al resumen</button></article>;
}
