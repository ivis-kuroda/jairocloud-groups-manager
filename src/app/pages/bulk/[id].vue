<script setup lang="ts">
const route = useRoute()
const historyId = computed(() => route.params.id as string)
const taskId = computed(() => route.query.taskId as string | undefined)

const { currentStep, items } = useBulk()
currentStep.value = 'result'
</script>

<template>
  <div>
    <UPageHeader
      :title="$t('bulk.title')" :description="$t('bulk.description')"
      :ui="{ root: 'py-2', description: 'mt-2' }"
    />

    <UStepper
      ref="stepper" v-model="currentStep" :items="items" disabled
      orientation="horizontal" class="my-8"
    />

    <BulkResultStep :history-id="historyId" :task-id="taskId" />
  </div>
</template>
