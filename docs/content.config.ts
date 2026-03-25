import { defineCollection, defineContentConfig } from '@nuxt/content'
import { z } from 'zod'

export default defineContentConfig({
  collections: {
    index: defineCollection({
      type: 'page',
      source: 'index.md',
    }),
    detailed: defineCollection({
      type: 'page',
      source: '01.detailed/**/*',
      schema: z.object({
        headline: z.string().optional(),
        icon: z.string().optional(),
      }),
    }),
    api: defineCollection({
      type: 'page',
      source: '02.api/**/*',
      schema: z.object({
        headline: z.string().optional(),
        icon: z.string().optional(),
      }),
    }),
    db: defineCollection({
      type: 'page',
      source: '03.db/**/*',
      schema: z.object({
        headline: z.string().optional(),
        icon: z.string().optional(),
      }),
    }),
    manual: defineCollection({
      type: 'page',
      source: '05.manual/**/*',
      schema: z.object({
        'headline': z.string().optional(),
        'icon': z.string().optional(),
        'system-admin-only': z.boolean().optional(),
      }),
    }),
  },
})
