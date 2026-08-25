---
name: firecrawl
description: Use the firecrawl MCP when searching for documentation or researching GitHub issues and pull requests. Trigger whenever you need library/framework docs, an API contract, an error message explained, a known bug, or the full context of a GitHub issue - especially before working on or opening a PR against an issue. Traditional web fetch tools miss issue comments, linked PRs, and duplicates; firecrawl's indexed search and scrape do not.
---

# Firecrawl MCP: docs and GitHub research

The firecrawl MCP server is available globally. Use it instead of generic web
fetch/search tools for two jobs:

1. **Documentation lookup** - library/framework docs, API contracts, error
   messages, known bugs.
2. **GitHub issue and PR research** - reading the full context of an issue
   (thread, comments, linked PRs) before acting on it.

Generic web tools return truncated GitHub pages and miss issue comments and
linked PRs. That has caused agents to open PRs against issues that already had
one. Firecrawl fixes this: use it every time GitHub issue context matters.

## Which tool to use

| Task | Tool |
| ---- | ---- |
| Programming question, docs, error message, known bug | `firecrawl_developer_search` - searches an index of GitHub issues, merged PRs, READMEs, and curated documentation sites. Start here. |
| Search GitHub issue/PR/README content in depth | `firecrawl_research_search_github` - returns full matched markdown, not just snippets. |
| Read one specific known URL (an issue thread, a docs page) | `firecrawl_scrape` - fetches the full page. Use for the complete issue thread including comments. |
| General web search with a developer/GitHub bias | `firecrawl_search` with `categories: ["developer"]` or `["github"]`. Fallback when the two searches above miss. |

## Before working on a GitHub issue (mandatory)

Agents have opened duplicate PRs because they never saw the full issue thread.
Before claiming an issue or opening a PR against it:

1. `firecrawl_scrape` the issue URL to read the **entire** thread: every
   comment, maintainer guidance, "I'm working on this" claims, and linked PRs.
2. `firecrawl_developer_search` or `firecrawl_research_search_github` for the
   issue number and title to find existing PRs, duplicates, and related
   discussion the thread itself doesn't link.
3. Only proceed if no open PR or active claim exists. If one does, report it
   instead of duplicating work.

## Credit discipline (important)

Firecrawl usage is metered per month. This skill exists for docs and GitHub
research only - stay inside that scope:

- Prefer **one targeted search or scrape** over multiple broad ones. Refine
  the query rather than firing several variations speculatively.
- **Do not use** `firecrawl_agent` (async research), `firecrawl_crawl`
  (multi-page collection), `firecrawl_map`, or any `firecrawl_monitor_*`
  tools unless the user explicitly asks. They are the expensive ones.
- Do not attach `scrapeOptions` to searches; scrape only the one result you
  actually need.
- For ordinary non-GitHub, non-docs pages, keep using the normal webfetch
  tool. Firecrawl is reserved for the two jobs above.
