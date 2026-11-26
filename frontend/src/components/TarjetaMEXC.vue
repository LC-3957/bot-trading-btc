<script setup lang="ts">
import type { CuentaMEXC } from '../api'

defineProps<{ c: CuentaMEXC | null; ultimaPrueba?: string | null }>()
</script>

<template>
  <section class="panel">
    <h2>Cuenta MEXC (spot)</h2>
    <div class="fila"><span>Conexión</span>
      <span :class="c?.conectada ? 'ok' : c?.configurada ? 'bad' : 'warn'">
        {{ !c ? '…' : c.conectada ? 'conectada' : c.configurada ? 'error al conectar' : 'sin claves en .env' }}</span></div>
    <div class="fila" v-if="c?.clave"><span>API key</span><span class="num">{{ c.clave }}</span></div>
    <div class="fila" v-if="c?.conectada"><span>Permisos</span><span>{{ (c.permisos ?? []).join(', ') || '—' }}{{ c.puede_operar ? ' · puede operar' : ' · sin permiso de trading' }}</span></div>
    <div class="fila" v-for="s in c?.saldos ?? []" :key="s.activo"><span>Saldo {{ s.activo }}</span>
      <span class="num">{{ s.libre.toLocaleString('es-MX', { maximumFractionDigits: 8 }) }}</span></div>
    <div class="fila"><span>Última orden de prueba</span>
      <span :class="ultimaPrueba?.startsWith('aceptada') ? 'ok' : ultimaPrueba ? 'bad' : ''">{{ ultimaPrueba ?? '—' }}</span></div>
    <p class="just">{{ c?.detalle }}</p>
  </section>
</template>
