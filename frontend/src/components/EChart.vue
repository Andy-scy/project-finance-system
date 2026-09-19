<script setup>
import * as echarts from 'echarts'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  option: { type: Object, required: true },
  height: { type: String, default: '300px' },
})
const el = ref(null)
let chart = null
let ro = null

onMounted(() => {
  chart = echarts.init(el.value)
  chart.setOption(props.option)
  ro = new ResizeObserver(() => chart && chart.resize())
  ro.observe(el.value)
})
watch(() => props.option, (o) => { if (chart) chart.setOption(o, true) }, { deep: true })
onBeforeUnmount(() => {
  if (ro) ro.disconnect()
  if (chart) chart.dispose()
})
</script>

<template>
  <div ref="el" :style="{ height, width: '100%' }" />
</template>
