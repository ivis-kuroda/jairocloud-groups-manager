// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  modules: [
    '@nuxt/eslint',
    '@nuxt/ui',
    '@pinia/nuxt',
    '@nuxtjs/i18n',
    '@nuxt/test-utils',
    '@vueuse/nuxt',
  ],
  ssr: false,

  imports: {
    dirs: ['~/types'],
    scan: true,
  },

  devtools: {
    enabled: true,
  },

  css: ['~/assets/css/main.css'],

  srcDir: 'src/app/',

  compatibilityDate: '2026-03-04',

  vite: {
    vue: {
      features: {
        optionsAPI: false,
      },
    },

  },

  eslint: {
    config: {
      stylistic: true,
    },
  },

  i18n: {
    locales: [
      { code: 'en', iso: 'es-US', file: 'en.json', name: 'English' },
      { code: 'ja', iso: 'ja-JP', file: 'ja.json', name: '日本語' },
    ],
    defaultLocale: 'ja',
    strategy: 'no_prefix',
    detectBrowserLanguage: {
      fallbackLocale: 'ja',
    },
    langDir: 'locales',
    restructureDir: 'src/app/i18n',
  },
})
