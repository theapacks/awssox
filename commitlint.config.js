module.exports = {
	extends: ["@commitlint/config-conventional"],
	rules: {
		"references-empty": [2, "never"], // Ensure references are present in commit messages
		"type-enum": [
			2,
			"always",
			[
				"build",
				"chore",
				"ci",
				"docs",
				"feat",
				"fix",
				"perf",
				"refactor",
				"revert",
				"style",
				"test",
			],
		],
		"subject-case": [2, "always", "sentence-case"],
		"footer-max-line-length": [1, "always", 100], // Warning for footer line length
		"body-max-line-length": [1, "always", 100], // Warning for body line length
		"header-max-length": [2, "always", 72],
		"subject-full-stop": [2, "never", "."],
		"type-case": [2, "always", "lower-case"],
		"scope-case": [2, "always", "lower-case"],
		"footer-leading-blank": [2, "always"], // Ensure blank line before footer
	},
};
