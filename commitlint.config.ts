import { RuleConfigSeverity } from '@commitlint/types'

import type { UserConfig } from '@commitlint/types'

const config: UserConfig = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'type-enum': [
      RuleConfigSeverity.Error,
      'always',
      [
        // default types
        'build',
        'chore',
        'ci',
        'docs',
        'feat',
        'fix',
        'perf',
        'refactor',
        'revert',
        'style',
        'test',
        // additional types
        'deps',
        'update',
        'remove',
        'hotfix',
        'rename',
        'move',
        'i18n',
      ],
    ],
  },
}

export default config
