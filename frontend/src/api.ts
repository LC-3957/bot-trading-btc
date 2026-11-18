// Cliente de la API del bot. La clave se escribe en la interfaz y se guarda solo en esta
// pestaña (sessionStorage); nunca va en el código ni en variables de Vite.

export interface Cartera { efectivo: number; cantidad: number; precio_entrada: number; posicion: number; dia: string }
export interface Ultimo {
  creado: string; fecha_vela: string; precio_ejecucion: number
  contexto: { pronostico: number; dist_sma20: number; vol20: number; rend_ultimo: number; cierre: number }
  propuesta: string | null; justificacion: string | null; latencia_s: number | null
  accion_final: string; aprobada: boolean; motivo: string
}
export interface Estado {
  version: string; modo: string; estado: 'DETENIDO' | 'CORRIENDO' | 'PAUSADO'; simbolo: string; intervalo: string
  modelo: { nombre: string; cargado: boolean; meta: Record<string, unknown> }
  llm: { modelo: string; local: boolean }
  cartera: Cartera; patrimonio: number; capital_inicial: number
  riesgo: { exposicion_max: number; perdida_diaria_max: number; antiguedad_max_h: number; costo: number; deslizamiento: number }
  ultimo: Ultimo | null
}
export interface Decision {
  id: number; fecha_vela: string; creado: string; pronostico: number; accion_propuesta: string | null
  justificacion: string | null; accion_final: string; aprobada: number; motivo: string; latencia_s: number | null
}
export interface ErrorBot { id: number; creado: string; etapa: string; tipo: string; mensaje: string }
export type Origen = 'vivo' | 'replay'
export interface Metricas {
  ciclos: number; latencia_media: number | null; latencia_max: number | null; sin_propuesta_valida: number | null
  rechazadas: number | null; pct_rechazadas: number | null; operaciones: number; errores: number
}
export interface FilaComparacion {
  estrategia: string; rendimiento_neto: number; max_drawdown: number; operaciones: number; operaciones_cerradas: number
  win_rate: number | null; patrimonio_final: number; latencia_media_s?: number | null; rechazadas?: number; propuestas_invalidas?: number
}
export interface Comparacion {
  periodo: [string, string] | null; ciclos: number; costo?: number; deslizamiento?: number; umbral_modelo?: number
  estrategias: FilaComparacion[]
}
export interface VelaG { fecha: string; open: number; high: number; low: number; close: number }
export interface OrdenG { id: number; fecha_vela: string; accion: 'COMPRAR' | 'VENDER'; precio: number; cantidad: number }
export interface Grafica { velas: VelaG[]; ordenes: OrdenG[] }

const CLAVE = 'bot_api_key'

export function leerClave(): string {
  try { return sessionStorage.getItem(CLAVE) ?? '' } catch { return '' }
}
export function guardarClave(v: string): void {
  try { sessionStorage.setItem(CLAVE, v) } catch { /* sin almacenamiento: se usa solo en memoria */ }
}

export class ApiError extends Error {
  constructor(public status: number, mensaje: string) { super(mensaje) }
}

async function pedir<T>(ruta: string, clave: string, metodo = 'GET'): Promise<T> {
  let r: Response
  try {
    r = await fetch(`/api${ruta}`, { method: metodo, headers: { 'X-API-Key': clave } })
  } catch {
    throw new ApiError(0, 'El backend no responde en 127.0.0.1:8000')
  }
  if (!r.ok) {
    const cuerpo = await r.json().catch(() => ({}))
    throw new ApiError(r.status, cuerpo.detail ?? `Error ${r.status}`)
  }
  return r.json() as Promise<T>
}

export async function descargarCsv(clave: string, tabla: string, origen: Origen): Promise<void> {
  const r = await fetch(`/api/exportar/${tabla}?origen=${origen}`, { headers: { 'X-API-Key': clave } })
  if (!r.ok) throw new ApiError(r.status, `No se pudo exportar ${tabla}`)
  const url = URL.createObjectURL(await r.blob())
  const a = document.createElement('a')
  a.href = url; a.download = `${tabla}_${origen}.csv`; a.click()
  URL.revokeObjectURL(url)
}

export const api = {
  estado: (k: string) => pedir<Estado>('/estado', k),
  decisiones: (k: string, o: Origen) => pedir<Decision[]>(`/decisiones?n=30&origen=${o}`, k),
  errores: (k: string, o: Origen) => pedir<ErrorBot[]>(`/errores?n=10&origen=${o}`, k),
  metricas: (k: string, o: Origen) => pedir<Metricas>(`/metricas?origen=${o}`, k),
  comparacion: (k: string, o: Origen) => pedir<Comparacion>(`/comparacion?origen=${o}`, k),
  grafica: (k: string, o: Origen) => pedir<Grafica>(`/grafica?origen=${o}&n=120`, k),
  control: (k: string, accion: 'iniciar' | 'pausar' | 'detener') => pedir<{ estado: string }>(`/control/${accion}`, k, 'POST'),
  ciclo: (k: string) => pedir<Record<string, unknown>>('/ciclo', k, 'POST'),
}
