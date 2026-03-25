<!--
 Copyright (C) 2026 National Institute of Informatics.
-->
<template>
  <UApp :toaster="{ position: 'top-center' }">
    <AppHeader />

    <UMain>
      <UContainer>
        <UPage>
          <UPageBody>
            <slot />
          </UPageBody>
        </UPage>
      </UContainer>
    </UMain>

    <AppFooter />
  </UApp>
</template>
