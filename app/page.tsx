"use client";

import { useMemo, useState } from "react";

const nav = ["Resumen", "Pacientes", "Exámenes", "Conversión", "Visor DICOM", "Documentos", "CRM", "Reportes", "Auditoría"];
const exams = [
  { patient: "María González", id: "12.345.678-5", study: "TC Tórax", files: 324, status: "Disponible", date: "31 jul, 10:42" },
  { patient: "James Wilson", id: "P USA 5839201", study: "Documentos clínicos", files: 18, status: "Procesando", date: "31 jul, 10:31" },
  { patient: "Paciente NN-024", id: "ID interno", study: "RX Extremidad", files: 4, status: "Disponible", date: "31 jul, 09:58" },
  { patient: "Ana Pérez Soto", id: "18.442.901-K", study: "Informe laboratorio", files: 12, status: "Revisión", date: "30 jul, 17:22" },
];

export default function Home() {
  const [active, setActive] = useState("Resumen");
  const [query, setQuery] = useState("");
  const [notice, setNotice] = useState("");
  const filtered = useMemo(() => exams.filter((x) => `${x.patient} ${x.id} ${x.study}`.toLowerCase().includes(query.toLowerCase())), [query]);

  const action = (message: string) => { setNotice(message); window.setTimeout(() => setNotice(""), 2600); };

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand"><span className="brandmark">D</span><div><strong>DICOM Flow</strong><small>Clínica Central</small></div></div>
        <nav>{nav.map((item, i) => <button key={item} className={active === item ? "active" : ""} onClick={() => { setActive(item); action(`${item}: módulo seleccionado`); }}><span>{["⌂","♙","▣","⇄","◫","□","◇","▥","◎"][i]}</span>{item}{item === "Conversión" && <b>3</b>}</button>)}</nav>
        <div className="storage"><div><span>Almacenamiento</span><strong>68%</strong></div><progress value="68" max="100"/><small>1,36 TB de 2 TB</small></div>
        <div className="profile"><div className="avatar">MC</div><div><strong>Manuel Castillo</strong><small>Administrador</small></div><button>•••</button></div>
      </aside>

      <section className="workspace">
        <header><div><p className="eyebrow">CENTRO DE OPERACIONES</p><h1>{active}</h1><p>Actividad clínica y documental en tiempo real</p></div><div className="headerActions"><button className="icon">⌕</button><button className="icon">♢<i /></button><button className="primary" onClick={() => action("Zona de carga preparada: JPG, PNG, PDF, TXT, CSV o DICOM")}>＋ Nueva conversión</button></div></header>

        <div className="stats">
          {[['Archivos convertidos','2.846','+12,4%','este mes'],['Pacientes activos','1.248','+38','últimos 30 días'],['En procesamiento','3','7 min','tiempo estimado'],['Almacenamiento','1,36 TB','68%','del total']].map((s, i) => <article key={s[0]}><div className={`statIcon c${i}`}>{['⇄','♙','◌','▤'][i]}</div><div><span>{s[0]}</span><strong>{s[1]}</strong><p><em>{s[2]}</em> {s[3]}</p></div>{i === 3 && <progress value="68" max="100"/>}</article>)}
        </div>

        <div className="grid">
          <article className="panel activity"><div className="panelHead"><div><h2>Actividad de conversiones</h2><p>Últimos 7 días</p></div><select aria-label="Periodo"><option>Esta semana</option></select></div><div className="chart"><div className="yaxis"><span>600</span><span>450</span><span>300</span><span>150</span><span>0</span></div><div className="bars">{[42,58,49,76,66,88,57].map((h,i)=><div key={i}><span className="bar" style={{height:`${h}%`}} title={`${h*6} archivos`} /><small>{['Lun','Mar','Mié','Jue','Vie','Sáb','Dom'][i]}</small></div>)}</div></div><div className="legend"><span><i className="blue"/>Convertidos <b>2.846</b></span><span><i className="green"/>Sin errores <b>98,7%</b></span><span><i className="orange"/>Con incidencias <b>1,3%</b></span></div></article>
          <article className="panel quick"><div className="panelHead"><div><h2>Acciones rápidas</h2><p>Flujos frecuentes</p></div></div>{[['⇧','Convertir archivos','Individual o carga por lote'],['♙','Registrar paciente','Con RUT, pasaporte u otro ID'],['◫','Abrir visor DICOM','Estudios recientes y herramientas'],['▥','Generar reporte','Operacional, clínico o auditoría']].map((a,i)=><button key={a[1]} onClick={()=>action(`${a[1]}: acción iniciada`)}><span className={`quickIcon q${i}`}>{a[0]}</span><div><strong>{a[1]}</strong><small>{a[2]}</small></div><b>›</b></button>)}</article>
        </div>

        <article className="panel recent"><div className="panelHead"><div><h2>Exámenes recientes</h2><p>Conversiones y estudios incorporados</p></div><div className="tableActions"><label>⌕ <input value={query} onChange={(e)=>setQuery(e.target.value)} placeholder="Buscar paciente o examen"/></label><button onClick={()=>action("Listado completo preparado")}>Ver todos</button></div></div><div className="tableWrap"><table><thead><tr><th>Paciente</th><th>Examen</th><th>Archivos</th><th>Estado</th><th>Fecha</th><th></th></tr></thead><tbody>{filtered.map((e)=><tr key={e.patient}><td><span className="patientDot">{e.patient.split(' ').map(x=>x[0]).slice(0,2)}</span><div><strong>{e.patient}</strong><small>{e.id}</small></div></td><td>{e.study}</td><td>{e.files}</td><td><span className={`status ${e.status.toLowerCase()}`}>● {e.status}</span></td><td>{e.date}</td><td><button className="more" onClick={()=>action(`Opciones para ${e.patient}`)}>•••</button></td></tr>)}</tbody></table></div></article>
        <footer><span><i/> Todos los servicios operativos</span><span>Última sincronización: hace 1 min</span></footer>
      </section>
      {notice && <div className="toast">✓ {notice}</div>}
    </main>
  );
}
