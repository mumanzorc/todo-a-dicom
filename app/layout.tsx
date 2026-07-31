import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = { title: "DICOM Flow | Gestión clínica", description: "Conversión, visualización y gestión segura de información clínica en DICOM." };
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="es"><body>{children}</body></html>}
