# Shared Instructions for AgentKernel

You are operating in the AgentKernel repository.

This project focuses on:
- Agent orchestration
- Tool execution pipelines
- Azure / OpenAI integrations
- Deterministic execution flows
- Structured, production-oriented code

Follow these rules strictly.

---

## 🔒 Safety & Scope Rules

- Do NOT modify infrastructure, CI/CD, GitHub workflows, or Azure configuration.
- Do NOT change authentication logic, secrets handling, or environment variable wiring.
- Do NOT introduce new dependencies unless absolutely required for documentation accuracy.
- Never rewrite large files unless explicitly necessary.
- Keep pull requests small and focused.

If unsure, prefer documenting instead of refactoring.

---

## 📚 Documentation Update Rules

When updating documentation:

- Only document features that actually exist in the repository.
- Do not invent APIs, configuration flags, or CLI options.
- Prefer minimal diffs.
- If behavior is unclear, inspect the actual implementation before documenting.
- Keep examples aligned with real code structure.

Use precise technical language. Avoid marketing tone.

---

## 🧠 Code Awareness Rules

Before documenting:
- Inspect function signatures.
- Verify environment variable names.
- Confirm Azure endpoint styles (v1 vs deployment-scoped).
- Check tool invocation formats.

Never assume model names or deployment names.

---

## 🛠 Agent & Tooling Conventions

AgentKernel is tool-driven and structured.

Respect:
- Existing module boundaries
- Clear separation between orchestration and execution layers
- Azure-specific configuration patterns
- Deterministic logging behavior

Avoid:
- Introducing hidden state
- Changing logging formats
- Renaming public interfaces

---

## 🧪 Pull Request Style

When creating a PR:

- Title prefix: `[docs]`
- Include a short explanation of:
  - What changed
  - Why it was needed
  - Files touched
- Keep PRs atomic.

---

## 🧾 Output Expectations

- Generate clean Markdown.
- Preserve formatting.
- Do not remove existing sections unless clearly obsolete.
- Avoid large rewrites.

---

## 🛑 If No Changes Are Needed

If no documentation updates are required:
- Explicitly state that the documentation is up to date.
- Do NOT create a pull request.

