<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { api, ApiError, descargarCsv, guardarClave, leerClave, type Comparacion, type Decision, type ErrorBot,
  type CuentaMEXC, type Estado, type Grafica, type Metricas, type Origen } from './api'
import GraficaPrecio from './components/GraficaPrecio.vue'
import PanelMetricas from './components/PanelMetricas.vue'
import TablaComparacion from './components/TablaComparacion.vue'
import TarjetaMEXC from './components/TarjetaMEXC.vue'

const clave = ref(leerClave())
const claveInput = ref('')
const estado = ref<Estado | null>(null)
const decisiones = ref<Decision[]>([])
const errores = ref<ErrorBot[]>([])
const origen = ref<Origen>('vivo')
const metricas = ref<Metricas | null>(null)
const comparacion = ref<Comparacion | null>(null)
const grafica = ref<Grafica | null>(null)
const cuentaMexc = ref<CuentaMEXC | null>(null)
let timerMexc: number | undefined

async function refrescarMexc() {
  if (!clave.value) return
  try { cuentaMexc.value = await api.mexc(clave.value) } catch { /* el aviso general ya muestra fallas del backend */ }
}
const aviso = ref('')
const ocupado = ref(false)
let timer: number | undefined

const usd = (v: number | null | undefined) =>
  v == null ? '—' : v.toLocaleString('es-MX', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 })
const pct = (v: number | null | undefined, d = 2) => (v == null ? '—' : `${(v * 100).toFixed(d)} %`)

const rendimiento = computed(() =>
  estado.value ? estado.value.patrimonio / estado.value.capital_inicial - 1 : null)
const claseEstado = computed(() =>
  ({ CORRIENDO: 'ok', PAUSADO: 'warn', DETENIDO: 'bad' } as const)[estado.value?.estado ?? 'DETENIDO'])

async function refrescar() {
  if (!clave.value) return
  try {
    const k = clave.value, o = origen.value
    const [e, d, er, m, c, g] = await Promise.all([api.estado(k), api.decisiones(k, o), api.errores(k, o),
      api.metricas(k, o), api.comparacion(k, o), api.grafica(k, o)])
    estado.value = e; decisiones.value = d; errores.value = er; metricas.value = m; comparacion.value = c; grafica.value = g
    if (aviso.value.startsWith('El backend')) aviso.value = ''
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) { clave.value = ''; aviso.value = 'Clave incorrecta.' }
    else aviso.value = (err as Error).message
  }
}

function entrar() {
  clave.value = claveInput.value.trim(); guardarClave(clave.value); claveInput.value = ''
  aviso.value = ''; refrescar(); refrescarMexc()
}

async function control(accion: 'iniciar' | 'pausar' | 'detener') {
  ocupado.value = true
  try { await api.control(clave.value, accion); await refrescar() }
  catch (err) { aviso.value = (err as Error).message }
  finally { ocupado.value = false }
}

async function cicloAhora() {
  ocupado.value = true
  try { const r = await api.ciclo(clave.value); aviso.value = `Ciclo: ${r.resultado}`; await refrescar() }
  catch (err) { aviso.value = (err as Error).message }
  finally { ocupado.value = false }
}

function verOrigen(o: Origen) { origen.value = o; refrescar() }

async function exportar(tabla: string) {
  try { await descargarCsv(clave.value, tabla, origen.value) } catch (err) { aviso.value = (err as Error).message }
}

onMounted(() => {
  refrescar(); refrescarMexc()
  timer = window.setInterval(refrescar, 5000)
  timerMexc = window.setInterval(refrescarMexc, 60000)          // la cuenta se consulta cada minuto
})
onUnmounted(() => { window.clearInterval(timer); window.clearInterval(timerMexc) })
</script>

<template>
  <main>
    <div class="barra">
      <h1>Bot de trading {{ estado?.simbolo ?? 'BTCUSDT' }} <small class="num">v{{ estado?.version ?? '0.3.0' }}</small></h1>
      <span v-if="estado" class="chip" :class="claseEstado">{{ estado.estado }}</span>
    </div>

    <section v-if="!clave" class="panel" style="margin-top:14px">
      <h2>Acceso</h2>
      <form class="barra" @submit.prevent="entrar">
        <input v-model="claveInput" type="password" placeholder="BOT_API_KEY (del archivo .env)" autocomplete="off" />
        <button class="primario" type="submit" :disabled="!claveInput">Entrar</button>
      </form>
    </section>

    <template v-else>
      <div class="panel barra" style="margin-top:14px">
        <div class="acciones">
          <button class="primario" :disabled="ocupado || estado?.estado === 'CORRIENDO'" @click="control('iniciar')">Iniciar</button>
          <button :disabled="ocupado || estado?.estado !== 'CORRIENDO'" @click="control('pausar')">Pausar</button>
          <button :disabled="ocupado || estado?.estado === 'DETENIDO'" @click="control('detener')">Detener</button>
          <button :disabled="ocupado || estado?.estado === 'DETENIDO'" @click="cicloAhora">Revisar vela ahora</button>
        </div>
        <span class="chip warn">MODO {{ estado?.modo ?? 'PAPER' }} · órdenes reales bloqueadas</span>
      </div>
      <div v-if="aviso" class="aviso">{{ aviso }}</div>

      <div class="grid" v-if="estado">
        <section class="panel">
          <h2>Datos y pronóstico</h2>
          <div class="fila"><span>Última vela cerrada</span><span class="num">{{ estado.ultimo?.fecha_vela ?? '—' }}</span></div>
          <div class="fila"><span>Cierre</span><span class="num">{{ usd(estado.ultimo?.contexto.cierre) }}</span></div>
          <div class="fila"><span>Pronóstico t+1</span><span class="num">{{ pct(estado.ultimo?.contexto.pronostico, 3) }}</span></div>
          <div class="fila"><span>Distancia a SMA20</span><span class="num">{{ pct(estado.ultimo?.contexto.dist_sma20) }}</span></div>
          <div class="fila"><span>Volatilidad 20 d</span><span class="num">{{ pct(estado.ultimo?.contexto.vol20) }}</span></div>
          <div class="fila"><span>Modelo</span><span :class="estado.modelo.cargado ? 'ok' : 'warn'">{{ estado.modelo.nombre }}</span></div>
        </section>

        <section class="panel">
          <h2>Decisión</h2>
          <div class="fila"><span>Propuesta del LLM</span><span>{{ estado.ultimo?.propuesta ?? '—' }}</span></div>
          <div class="fila"><span>Acción final</span>
            <span :class="estado.ultimo?.aprobada ? 'ok' : 'bad'">{{ estado.ultimo?.accion_final ?? '—' }}</span></div>
          <div class="fila"><span>Riesgo</span><span>{{ estado.ultimo?.motivo ?? '—' }}</span></div>
          <div class="fila"><span>LLM local</span><span>{{ estado.llm.modelo }}</span></div>
          <div class="fila"><span>Latencia</span><span class="num">{{ estado.ultimo?.latencia_s != null ? estado.ultimo.latencia_s.toFixed(1) + ' s' : '—' }}</span></div>
          <p class="just" v-if="estado.ultimo?.justificacion">“{{ estado.ultimo.justificacion }}”</p>
        </section>

        <section class="panel">
          <h2>Posición y patrimonio</h2>
          <div class="fila"><span>Patrimonio</span><span class="num">{{ usd(estado.patrimonio) }}</span></div>
          <div class="fila"><span>Rendimiento</span>
            <span class="num" :class="(rendimiento ?? 0) >= 0 ? 'ok' : 'bad'">{{ pct(rendimiento) }}</span></div>
          <div class="fila"><span>Efectivo (USDT)</span><span class="num">{{ usd(estado.cartera.efectivo) }}</span></div>
          <div class="fila"><span>BTC</span><span class="num">{{ estado.cartera.cantidad.toFixed(6) }}</span></div>
          <div class="fila"><span>Posición</span><span>{{ estado.cartera.posicion ? 'Comprado' : 'En efectivo' }}</span></div>
          <div class="fila"><span>Límites</span>
            <span class="num">exp. {{ pct(estado.riesgo.exposicion_max, 0) }} · pérdida/día {{ pct(estado.riesgo.perdida_diaria_max, 0) }}</span></div>
        </section>
      </div>
      <div class="grid"><TarjetaMEXC :c="cuentaMexc" :ultima-prueba="estado?.ultimo?.mexc_prueba" /></div>

      <div class="panel barra" style="margin-top:14px">
        <span>Ver evidencia de:</span>
        <div class="acciones">
          <button :class="{ primario: origen === 'vivo' }" @click="verOrigen('vivo')">Operación en vivo</button>
          <button :class="{ primario: origen === 'replay' }" @click="verOrigen('replay')">Replay histórico</button>
        </div>
      </div>

      <div style="margin-top:14px"><GraficaPrecio :datos="grafica" :simbolo="estado?.simbolo ?? 'BTCUSDT'" /></div>
      <div class="grid">
        <PanelMetricas :m="metricas" :origen="origen" @exportar="exportar" />
        <div class="ancho2"><TablaComparacion :c="comparacion" /></div>
      </div>

      <section class="panel" style="margin-top:14px">
        <h2>Historial de decisiones · {{ origen === 'vivo' ? 'en vivo' : 'replay' }}</h2>
        <div class="tabla-wrap">
          <table class="tabla">
            <thead><tr><th>Vela</th><th>Pronóstico</th><th>LLM</th><th>Final</th><th>Motivo</th><th>Latencia</th></tr></thead>
            <tbody>
              <tr v-for="d in decisiones" :key="d.id">
                <td class="num">{{ d.fecha_vela }}</td><td class="num">{{ pct(d.pronostico, 3) }}</td>
                <td>{{ d.accion_propuesta ?? '—' }}</td>
                <td :class="d.aprobada ? 'ok' : 'bad'">{{ d.accion_final }}</td>
                <td>{{ d.motivo }}</td><td class="num">{{ d.latencia_s != null ? d.latencia_s.toFixed(1) + ' s' : '—' }}</td>
              </tr>
              <tr v-if="!decisiones.length"><td colspan="6">Sin decisiones todavía.</td></tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="panel" style="margin-top:14px">
        <h2>Errores recientes</h2>
        <div class="tabla-wrap">
          <table class="tabla">
            <thead><tr><th>Hora (UTC)</th><th>Etapa</th><th>Tipo</th><th>Mensaje</th></tr></thead>
            <tbody>
              <tr v-for="e in errores" :key="e.id"><td class="num">{{ e.creado }}</td><td>{{ e.etapa }}</td><td>{{ e.tipo }}</td><td>{{ e.mensaje }}</td></tr>
              <tr v-if="!errores.length"><td colspan="4">Sin errores.</td></tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </main>
</template>
