# Split Integration Into Separate Repo

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move the custom integration into its own GitHub repo so HACS can discover it separately from the addon.

**Architecture:** Create `slayer/zeroclaw-homeassistant-integration` with `custom_components/zeroclaw/` and `hacs.json`. Remove integration files from this addon repo. Update READMEs in both repos to cross-reference each other.

**Tech Stack:** GitHub CLI (`gh`), git

---

### Task 1: Create the new integration repo on GitHub

**Step 1: Create repo**

```bash
gh repo create slayer/zeroclaw-homeassistant-integration \
  --public \
  --description "ZeroClaw Assistant custom integration for Home Assistant (HACS-compatible)" \
  --clone
```

**Step 2: Verify**

```bash
gh repo view slayer/zeroclaw-homeassistant-integration
```

Expected: repo exists, public, empty.

---

### Task 2: Populate the new integration repo

**Step 1: Copy integration files**

Copy `custom_components/zeroclaw/` from this repo into the new repo, preserving directory structure.

**Step 2: Create `hacs.json`**

```json
{
  "name": "ZeroClaw Assistant",
  "render_readme": true
}
```

**Step 3: Create `README.md`**

Content should cover:
- What this integration does (connects HA to ZeroClaw daemon)
- Prerequisite: the addon must be installed from `slayer/zeroclaw-homeassistant`
- HACS install: add this repo as custom repository (category: Integration)
- Manual install: copy `custom_components/zeroclaw/` to HA config
- Configuration: Settings → Devices & Services → Add Integration → ZeroClaw
- What you get: conversation agent, sensors, services (reuse from current README)
- Link to addon repo

**Step 4: Commit and push**

```bash
git add -A && git commit -m "feat: initial integration extracted from addon repo"
git push -u origin master
```

---

### Task 3: Clean up the addon repo

**Files:**
- Delete: `custom_components/` (entire directory)
- Delete: `hacs.json`
- Modify: `README.md`

**Step 1: Remove integration files**

```bash
rm -rf custom_components/ hacs.json
```

**Step 2: Update README.md**

- Remove "Integration" from title (now just "ZeroClaw Home Assistant Addon")
- Add prominent note at top: integration required, link to new repo
- Remove HACS installation section
- Remove integration configuration section
- Remove "What You Get" section (entities, services, conversation agent)
- Keep: addon installation, addon configuration options, supported architectures, troubleshooting (addon-specific items only)

**Step 3: Update CLAUDE.md**

Remove references to `custom_components/zeroclaw/` since it no longer lives here.

**Step 4: Commit**

```bash
git add -A && git commit -m "refactor: move integration to slayer/zeroclaw-homeassistant-integration"
```
