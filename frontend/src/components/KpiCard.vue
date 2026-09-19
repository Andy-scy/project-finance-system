<script setup>
defineProps({
  label: String,
  value: [String, Number],
  unit: { type: String, default: '万元' },
  extra: String,
  tone: { type: String, default: '' }, // '' | danger | success | warn
  accent: Boolean,
})
</script>

<template>
  <div class="kpi-card" :class="[tone, { accent }]">
    <div class="label">{{ label }}</div>
    <div class="value num">{{ value }}<span v-if="unit" class="unit">{{ unit }}</span></div>
    <div v-if="extra" class="extra">{{ extra }}</div>
  </div>
</template>
