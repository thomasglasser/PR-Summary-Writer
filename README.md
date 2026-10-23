# PR Summary Writer 📝

**PR Summary Writer** is an autonomous AI assistant for GitHub Pull Requests that generates high-level, conceptual summaries and domain-grouped changelogs. It automatically analyzes PR diffs to explain *what* changed, *how* the system behaves differently, and *why* architectural shifts were made, updating the PR description in-place on every push while strictly preserving developer notes and manual rationale.

---

## ✨ Features

- **🎯 Conceptual & Thematic**: Synthesizes the core architectural intent and behavioural impact of changes rather than generating noisy line-by-line diff dumps.
- **🏷️ Domain-Grouped Changelogs**: Organizes modifications into logical, functional feature domains (e.g. Lifecycle Management, Network Synchronization, Cache & Invalidation, Safeguards) instead of an unorganized laundry list of files.
- **🛡️ In-Place Note Preservation**: Anchors generated text between `<!-- PR-SUMMARY-WRITER:START -->` and `<!-- PR-SUMMARY-WRITER:END -->`. Developer notes, architectural reasoning, and checklists are **never overwritten or deleted**.
- **🔄 Continuous Updates**: Automatically re-synthesizes and updates the PR description whenever new commits are pushed, keeping reviewer context fresh.
- **⚡ Reusable GitHub Action**: Integrates into any repository with just a tiny ~15 line workflow file.

---

## 🚀 Quick Start & Integration

Add the following workflow to your repository at `.github/workflows/pr_summary.yml`:

```yaml
name: PR Summary Writer

on:
  pull_request:
    types: [opened, synchronize, reopened]
  issue_comment:
    types: [created]

jobs:
  summarize:
    # Trigger on PR lifecycle events or when a contributor comments /summarize
    if: |
      github.event_name == 'pull_request' ||
      ((github.event.comment.user.type != 'Bot' && !endsWith(github.actor, '[bot]')) &&
       (contains(github.event.comment.body, '/summarize') || contains(github.event.comment.body, '/summary')))
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
      issues: write

    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Generate PR Summary
        uses: thomasglasser/pr-summary-writer@main
        with:
          app-id: ${{ secrets.PR_SUMMARY_WRITER_APP_ID }}
          private-key: ${{ secrets.PR_SUMMARY_WRITER_PRIVATE_KEY }}
          gemini-api-key: ${{ secrets.PR_SUMMARY_WRITER_API_KEY || secrets.GEMINI_API_KEY }}
```

---

## 💬 Slash Commands

Maintainers and contributors can trigger or refresh the summary directly in PR comment threads:

| Command | Description | Example |
| :--- | :--- | :--- |
| `/summarize` | Generates or refreshes the automated PR summary for this pull request. | `/summarize` |
| `/summary` | Alias for `/summarize`. | `/summary` |

---

## 📝 Preserving Developer Notes

When opening a Pull Request, developers can write any manual notes, architectural rationale, or checklists. PR Summary Writer detects existing text and places its automated summary cleanly below:

```markdown
## Developer Notes & Rationale
Decoupled auth tokens from user session storage to prevent race conditions during distributed replication.

<!-- PR-SUMMARY-WRITER:START -->
## Summary
This Pull Request introduces significant improvements to distributed session management and token validation...

## Main Changes
### Session and Token Lifecycle Updates
- Introduced distributed session leasing, marking sessions appropriately when connections drop or workers restart.
- Enhanced mechanisms to recall expired leases or reconcile inconsistent states upon cluster rejoin.
<!-- PR-SUMMARY-WRITER:END -->
```

On every subsequent push (`synchronize`), only the content bounded by the comment tags is updated. Everything outside the tags remains completely untouched.

---

## 📄 License

GNU General Public License v3.0 (GPL-3.0). See [LICENSE](LICENSE) for details.
