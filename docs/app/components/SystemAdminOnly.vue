<script setup lang="ts">
const { systemAdminVisible } = useSystemAdminVisibility()
</script>

<template>
  <div v-if="systemAdminVisible">
    <slot />
  </div>
</template>
