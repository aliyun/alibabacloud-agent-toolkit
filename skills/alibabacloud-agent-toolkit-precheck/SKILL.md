---
name: alibabacloud-agent-toolkit-precheck
description: >
  Pre-installation environment check and setup for Alibaba Cloud Agent Toolkit.
  Verifies and installs prerequisites: uv, Alibaba Cloud CLI (aliyun),
  CLI authentication, openapiexplorer plugin, and MCP Server Core.
  Use when: alibabacloud agent toolkit install, environment check, prerequisite check,
  setup alibabacloud, precheck, plugin install, toolkit setup, mcp core setup,
  aliyun CLI setup.
license: Apache-2.0
metadata:
  domain: environment-setup
  owner: sdk-team
---

# Alibaba Cloud Agent Toolkit — Pre-Installation Environment Check

This skill validates and sets up all prerequisites required to run the Alibaba Cloud
Agent Toolkit MCP plugins. Execute each step **in order** — later steps depend on
earlier ones.

## Safety Policy

Each step is classified by risk level. Follow these rules strictly:

| Classification | Agent behavior |
|----------------|----------------|
| **Auto** (read-only check) | Execute without asking. |
| **Confirm** (local install / CLI plugin install) | Show the user the exact command, explain what it does, and **wait for explicit approval** before executing. Never pipe-to-shell silently. |
| **User-only** (interactive / browser-based) | Display instructions for the user to run in a **separate terminal**. Do not attempt to execute. |
| **Confirm-cloud** (cloud-side write) | Explain the cloud resource that will be created, then **wait for explicit approval** before executing. |

---

## Checklist Overview

Run through these steps sequentially. **Skip any step whose check already passes.**

1. [Check / Install `uv`](#step-1-uv) — Confirm
2. [Check / Install Alibaba Cloud CLI (`aliyun`)](#step-2-aliyun-cli) — Confirm
3. [Check CLI authentication](#step-3-cli-authentication) — Auto (check) / User-only (login)
4. [Check / Install `openapiexplorer` plugin](#step-4-openapiexplorer-plugin) — Confirm
5. [Check / Create MCP Server Core](#step-5-mcp-server-core) — Auto (check) / Confirm-cloud (create)

---

## Step 1: `uv` {#step-1-uv}

`uv` is the Python package manager required to start MCP servers.

### Check (Auto)

```bash
uv --version
```

- **Pass** → output shows a version string (e.g. `uv 0.6.x`). Proceed to Step 2.
- **Fail** → `command not found`. Install below.

### Install (Confirm — ask user before executing)

Present the appropriate command to the user and **wait for approval**:

| Platform        | Command |
|-----------------|---------|
| macOS / Linux   | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Windows (PowerShell) | `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 \| iex"` |

> **Security note:** These are pipe-to-shell commands. Show the command to the user
> and let them decide whether to run it. Do not execute without explicit consent.

After installation, verify with `uv --version`. If the shell cannot find `uv`,
instruct the user to restart their terminal or source their shell profile
(`source ~/.bashrc`, `source ~/.zshrc`, etc.) so the PATH update takes effect.

---

## Step 2: Alibaba Cloud CLI (`aliyun`) {#step-2-aliyun-cli}

### Check (Auto)

```bash
aliyun version
```

- **Pass** → outputs a version string (e.g. `3.x.x`). Proceed to Step 3.
- **Fail** → `command not found`. Install below.

### Install (Confirm — ask user before executing)

Present the appropriate command to the user and **wait for approval**:

#### macOS / Linux

```bash
/bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"
```

> **Security note:** This is a pipe-to-shell command. Show the command and let the
> user decide. Do not execute without explicit consent.

#### Windows (PowerShell)

The installer script is located at [`scripts/install-aliyun-cli-windows.ps1`](scripts/install-aliyun-cli-windows.ps1).

Instruct the user to download or copy the script, then run:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\install-aliyun-cli-windows.ps1
```

After installation, verify with `aliyun version`. If the command is not found,
instruct the user to open a new terminal session so the updated PATH takes effect.

---

## Step 3: CLI Authentication {#step-3-cli-authentication}

### Check (Auto)

```bash
aliyun sts get-caller-identity
```

- **Pass** → returns JSON containing `AccountId`, `Arn`, and `UserId`. Proceed to Step 4.
- **Fail** → error response (e.g. `InvalidAccessKeyId`, `ERROR: ...`,
  or similar). Guide the user through OAuth login below.

### OAuth Login (User-only — user must run in a separate terminal)

The OAuth login flow is **interactive** — it opens a browser. The agent **must not**
attempt to execute this. Display the following instructions for the user:

```
Please run this command in a separate terminal:

    aliyun configure --mode OAuth --profile <ProfileName>

Replace <ProfileName> with a name of your choice (e.g. "default", "china", "myprofile").
This will open a browser for Alibaba Cloud login. Follow the prompts to complete authentication.
```

After the user confirms they have completed the OAuth flow, set the profile as current
and re-run the check:

```bash
aliyun configure set --current <ProfileName>
aliyun sts get-caller-identity
```

If it still fails, suggest the user verify their profiles:

```bash
aliyun configure list
```

---

## Step 4: `openapiexplorer` Plugin {#step-4-openapiexplorer-plugin}

### Check (Auto)

```bash
aliyun plugin show --name openapiexplorer
```

- **Pass** → outputs plugin metadata (name, version, etc.). Proceed to Step 5.
- **Fail** → `plugin not found` or error. Install below.

### Install (Confirm — ask user before executing)

```bash
aliyun plugin install --name openapiexplorer
```

After installation, re-run the check command to verify.

---

## Step 5: MCP Server Core {#step-5-mcp-server-core}

The MCP Server Core is a cloud-side resource that can only be created **once** per account.

### Check (Auto)

```bash
aliyun openapiexplorer list-api-mcp-server-cores --region cn-hangzhou
```

- **Pass** → response contains `"totalCount": 1`. The MCP Core already exists. **Done — all
  prerequisites are satisfied.**
- **Fail (totalCount 0)** → no core exists. Create one below.
- **Fail (permission error)** → the user's RAM identity lacks the required permission.
  See [Permission Error](#permission-error) below.

### Create (Confirm-cloud — ask user before executing)

This will create a cloud-side MCP Server Core resource in the user's Alibaba Cloud
account (region: cn-hangzhou). **Explain this to the user and wait for explicit approval.**

```bash
aliyun openapiexplorer create-api-mcp-server-core --region cn-hangzhou
```

Possible outcomes:

| Result | Meaning | Action |
|--------|---------|--------|
| Success (200) | Core created | Re-run the check to confirm `totalCount: 1` |
| Quota exceeded error | Core already exists (only one allowed) | Treat as success — the core is already provisioned |
| Permission denied / Forbidden | Missing RAM permission | See below |

### Permission Error {#permission-error}

If the user receives a permission error when listing or creating the MCP Core, they need
the following **system policy** attached to their RAM identity:

```
AliyunOpenAPIMCPServerStaticCredentialAccess
```

Instruct the user (or their account administrator) to:

1. Go to the [RAM Console](https://ram.console.aliyun.com/)
2. Find the RAM user or role in use
3. Attach the system policy **AliyunOpenAPIMCPServerStaticCredentialAccess**
4. Re-run the check / create commands

---

## Completion

When all five steps pass, report a summary:

```
Environment check complete — all prerequisites satisfied:
  ✓ uv installed
  ✓ Alibaba Cloud CLI installed
  ✓ CLI authenticated
  ✓ openapiexplorer plugin installed
  ✓ MCP Server Core provisioned
```

The user is now ready to install and use Alibaba Cloud Agent Toolkit plugins.
