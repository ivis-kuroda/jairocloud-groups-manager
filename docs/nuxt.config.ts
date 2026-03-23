// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  modules: [
    '@nuxt/ui',
    '@nuxt/content',
  ],

  ssr: true,
  devtools: { enabled: true },
  css: ['~/assets/css/main.css'],

  content: {
    build: {
      markdown: {
        highlight: {
          theme: {
            default: 'github-light',
            light: 'github-light',
            dark: 'github-dark',
          },
          langs: ['python', 'json'],
        },
      },
    },
  },
  devServer: { port: 4040 },

  compatibilityDate: '2025-01-15',
  nitro: {
    prerender: {
      crawlLinks: true,
      routes: ['/'],
    },
  },
})
