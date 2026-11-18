<script setup lang="ts">
import { computed } from 'vue'
import type { Grafica } from '../api'

const props = defineProps<{ datos: Grafica | null; simbolo: string }>()
const W = 760, H = 240, PAD = { l: 58, r: 12, t: 12, b: 26 }

const dibujo = computed(() => {
  const velas = props.datos?.velas ?? []
  if (velas.length < 2) return null
  const lows = velas.map((v) => v.low), highs = velas.map((v) => v.high)
  const min = Math.min(...lows), max = Math.max(...highs), rango = max - min || 1
  const x = (i: number) => PAD.l + (i * (W - PAD.l - PAD.r)) / (velas.length - 1)
  const y = (p: number) => PAD.t + ((max - p) * (H - PAD.t - PAD.b)) / rango
  const idx = new Map(velas.map((v, i) => [v.fecha, i]))
  const marcas = (props.datos?.ordenes ?? []).flatMap((o) => {
    const i = idx.get(o.fecha_vela)
    if (i === undefined) return []
    const j = Math.min(i + 1, velas.length - 1)          // se ejecuta en la apertura de la vela siguiente
    return [{ x: x(j), y: y(o.precio), compra: o.accion === 'COMPRAR', texto: `${o.accion} ${o.fecha_vela} @ ${o.precio.toFixed(2)}` }]
  })
  const ticks = [max, (max + min) / 2, min].map((p) => ({ y: y(p), texto: p.toLocaleString('es-MX', { maximumFractionDigits: 0 }) }))
  return {
    linea: velas.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v.close).toFixed(1)}`).join(' '),
    marcas, ticks, desde: velas[0]!.fecha, hasta: velas[velas.length - 1]!.fecha,
  }
})
</script>

<template>
  <section class="panel">
    <h2>Precio {{ simbolo }} y operaciones</h2>
    <svg v-if="dibujo" :viewBox="`0 0 ${W} ${H}`" width="100%" role="img" :aria-label="`Cierres de ${simbolo} con compras y ventas`">
      <g v-for="t in dibujo.ticks" :key="t.texto">
        <line :x1="PAD.l" :x2="W - PAD.r" :y1="t.y" :y2="t.y" stroke="currentColor" stroke-opacity=".12" />
        <text :x="PAD.l - 6" :y="t.y + 4" text-anchor="end" font-size="11" fill="currentColor" opacity=".6">{{ t.texto }}</text>
      </g>
      <path :d="dibujo.linea" fill="none" stroke="var(--accent)" stroke-width="1.8" />
      <g v-for="(m, k) in dibujo.marcas" :key="k">
        <polygon v-if="m.compra" :points="`${m.x},${m.y - 9} ${m.x - 6},${m.y + 3} ${m.x + 6},${m.y + 3}`" fill="var(--ok)"><title>{{ m.texto }}</title></polygon>
        <polygon v-else :points="`${m.x},${m.y + 9} ${m.x - 6},${m.y - 3} ${m.x + 6},${m.y - 3}`" fill="var(--bad)"><title>{{ m.texto }}</title></polygon>
      </g>
      <text :x="PAD.l" :y="H - 6" font-size="11" fill="currentColor" opacity=".6">{{ dibujo.desde }}</text>
      <text :x="W - PAD.r" :y="H - 6" font-size="11" fill="currentColor" opacity=".6" text-anchor="end">{{ dibujo.hasta }}</text>
    </svg>
    <p v-else class="just">Aún no hay velas guardadas para graficar.</p>
    <p class="just"><span class="ok">▲ compra</span> · <span class="bad">▼ venta</span> · se marcan en la apertura de la vela siguiente a la decisión.</p>
  </section>
</template>
