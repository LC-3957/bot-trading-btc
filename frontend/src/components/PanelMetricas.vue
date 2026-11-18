<script setup lang="ts">
import type { Metricas, Origen } from '../api'

defineProps<{ m: Metricas | null; origen: Origen }>()
const emit = defineEmits<{ exportar: [tabla: string] }>()
const pct = (v: number | null | undefined) => (v == null ? '—' : `${(v * 100).toFixed(1)} %`)
const seg = (v: number | null | undefined) => (v == null ? '—' : `${v.toFixed(1)} s`)
</script>

<template>
  <section class="panel">
    <h2>Evidencia · {{ origen === 'vivo' ? 'en vivo' : 'replay' }}</h2>
    <div class="fila"><span>Ciclos válidos registrados</span>
      <span class="num" :class="(m?.ciclos ?? 0) >= 20 ? 'ok' : 'warn'">{{ m?.ciclos ?? 0 }} / 20</span></div>
    <div class="fila"><span>Latencia del LLM (media · máx.)</span><span class="num">{{ seg(m?.latencia_media) }} · {{ seg(m?.latencia_max) }}</span></div>
    <div class="fila"><span>Propuestas rechazadas</span><span class="num">{{ m?.rechazadas ?? 0 }} ({{ pct(m?.pct_rechazadas) }})</span></div>
    <div class="fila"><span>Sin propuesta válida del LLM</span><span class="num">{{ m?.sin_propuesta_valida ?? 0 }}</span></div>
    <div class="fila"><span>Operaciones simuladas</span><span class="num">{{ m?.operaciones ?? 0 }}</span></div>
    <div class="fila"><span>Errores registrados</span><span class="num">{{ m?.errores ?? 0 }}</span></div>
    <div class="acciones" style="margin-top:10px">
      <button v-for="t in ['decisiones', 'ordenes', 'patrimonio', 'errores']" :key="t" @click="emit('exportar', t)">CSV {{ t }}</button>
    </div>
  </section>
</template>
