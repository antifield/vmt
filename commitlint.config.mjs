export default {
  extends: ['@commitlint/config-conventional'],
  parserPreset: {
    parserOpts: {
      // conventional commits, with an optional [no ci] prefix allowed at the
      // very start, e.g. "[no ci] docs: fix a typo"
      headerPattern: /^(?:\[no ci\] )?(\w+)(?:\(([^)]*)\))?(!)?: (.+)$/,
      headerCorrespondence: ['type', 'scope', 'breaking', 'subject'],
    },
  },
};
