// @ts-check
import unicorn from 'eslint-plugin-unicorn'

import withNuxt from './.nuxt/eslint.config.mjs'

export default withNuxt(
  // Your custom configs here
  unicorn.configs.recommended,
  {
    name: 'stylistic',
    rules: {
      'camelcase': ['error', { properties: 'always' }],
      'no-console': 'error',
      'vue/first-attribute-linebreak': ['error', { singleline: 'beside', multiline: 'below' }],
      'vue/max-attributes-per-line': [
        'warn', { singleline: { max: 4 }, multiline: { max: 4 } },
      ],
      '@stylistic/function-call-spacing': ['error', 'never'],
      '@stylistic/max-len': ['error', { code: 100 }],
    },
  },
  {
    name: 'coding',
    rules: {
      '@typescript-eslint/ban-ts-comment': [
        'error', { 'ts-expect-error': 'allow-with-description' },
      ],
    },
  },
  {
    name: 'sort-imports',
    rules: {
      'sort-imports': ['error', {
        ignoreCase: false,
        ignoreDeclarationSort: true,
        ignoreMemberSort: false,
      }],
      'import/order': ['error', {
        'groups': [
          'builtin', 'external', 'internal', 'parent', 'sibling', 'index', 'object', 'type',
        ],
        'newlines-between': 'always',
        'pathGroups': [
          {
            pattern: '{#**,@@/**,@/**}',
            group: 'internal',
            position: 'after',
          },
        ],
        'pathGroupsExcludedImportTypes': ['builtin'],
      }],
    },
  },
  {
    files: ['**/app/**/*.vue'],
    rules: {
      'unicorn/filename-case': [
        'error', { case: 'pascalCase', ignore: ['app.vue'] },
      ],
      'vue/no-multiple-template-root': 'off',
    },
  },
  {
    files: ['**/app/**/*.{ts,js}'],
    rules: {
      'unicorn/filename-case': ['error', { case: 'camelCase' }],
    },
  },
  {
    files: ['**/app/{pages,layouts}/**/*.vue', '**/app/{plugins,middleware}/**/*.ts'],
    rules: {
      'vue/multi-word-component-names': 'off',
      'unicorn/filename-case': ['error', { case: 'kebabCase' }],
    },
  },
)
