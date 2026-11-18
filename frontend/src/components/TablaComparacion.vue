<script setup lang="ts">
import type { Comparacion } from '../api'

defineProps<{ c: Comparacion | null }>()
const pct = (v: number | null | undefined) => (v == null ? '—' : `${(v * 100).toFixed(2)} %`)
</script>

<template>
  <section class="panel">
    <h2>Comparación del protocolo</h2>
    <p v-if="!c || !c.ciclos" class="just">Se calcula cuando haya ciclos registrados (en vivo o replay).</p>
    <template v-else>
      <p class="just">Periodo {{ c.periodo?.[0] }} a {{ c.periodo?.[1] }} · {{ c.ciclos }} ciclos · mismo costo ({{ pct(c.costo) }}) y deslizamiento ({{ pct(c.deslizamiento) }}) para las tres.</p>
      <div class="tabla-wrap">
        <table class="tabla">
          <thead><tr><th>Estrategia</th><th>Rend. neto</th><th>Máx. drawdown</th><th>Operaciones</th><th>Win Rate</th><th>Latencia</th><th>Rechazadas</th></tr></thead>
          <tbody>
            <tr v-for="f in c.estrategias" :key="f.estrategia">
              <td>{{ f.estrategia }}</td>
              <td class="num" :class="f.rendimiento_neto >= 0 ? 'ok' : 'bad'">{{ pct(f.rendimiento_neto) }}</td>
              <td class="num">{{ pct(f.max_drawdown) }}</td><td class="num">{{ f.operaciones }}</td>
              <td class="num">{{ pct(f.win_rate) }}</td>
              <td class="num">{{ f.latencia_media_s != null ? `${f.latencia_media_s.toFixed(1)} s` : '—' }}</td>
              <td class="num">{{ f.rechazadas ?? '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </section>
</template>
