---
name: alibabacloud-ecs-instance-ops
description: |
  Alibaba Cloud ECS instance lifecycle operations. Use for creating, starting, stopping,
  restarting, releasing, and querying ECS instances. Covers instance status management,
  batch operations, and instance attribute modification.
  Triggers: "ecs instance", "create instance", "start instance", "stop instance",
  "restart instance", "release instance", "query instance", "ecs ops", "ecs lifecycle".
source: alibabacloud-ecs-ops
---

# ECS Instance Lifecycle Operations

Manage the full lifecycle of Alibaba Cloud ECS instances: create, start, stop, restart, release, and query.

> **Pre-check: Alibaba Cloud CLI must be installed and at least version 3.3.3.**

```bash
aliyun version   # must be >= 3.3.3; if not installed:
/bin/bash -c "$(curl -fsSL --connect-timeout 10 --max-time 120 https://aliyuncli.alicdn.com/setup.sh)"
```

> **Pre-check: Alibaba Cloud Credentials Required**
>
> **Security Rules:**
> - **NEVER** read, echo, or print AK/SK values
> - **NEVER** ask the user to input AK/SK directly
> - **NEVER** use `aliyun configure set` with literal credential values
> - **ONLY** use `aliyun configure list` to check credential status
>
> ```bash
> aliyun configure list
> ```
> If no valid profile exists, STOP and guide user to configure credentials.

> **Pre-check: Aliyun CLI plugin update required**
> ```bash
> aliyun configure set --auto-plugin-install true
> aliyun plugin update
> ```

## Observability (MUST follow for every aliyun command)

Upon loading this skill, generate a random session ID (32-char lowercase hex string) once for the entire session. Use it as `{session-id}` below.

**Rule: Every `aliyun` CLI command that calls a cloud API MUST include the `--user-agent` flag.**

```
--user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-instance-ops/{session-id}
```

## Cost Estimation (MUST before chargeable operations)

Before executing any chargeable instance operation (run-instances, modify-instance-spec, modify-instance-charge-type), you **MUST** follow the `alibabacloud-cli-cost-estimation` skill to evaluate the cost impact at the **user task level**:

1. **Single operation** — Append `--estimate-cost` to the exact command before execution, present the quoted amount, and wait for user confirmation.
2. **Multi-step task** (e.g. stop + change spec + start) — Quote **all** chargeable steps up front using `--estimate-cost` and `--estimate-cost-context` as needed, present one consolidated cost plan, then ask for a **single confirmation** of the whole task before executing step 1.
3. **Never silently execute** a chargeable instance operation when a cost quote was obtainable.

> The cost evaluation output **must** include a clearly labelled cost summary section so the user can identify it before confirming.

See the `alibabacloud-cli-cost-estimation` SKILL.md for the full cost plan format, quote JSON parsing, and multi-step workflow quoting rules.

## Core Workflow

> **IMPORTANT: Parameter Confirmation** — Before executing any command or API call,
> ALL user-customizable parameters (e.g., RegionId, instance names, CIDR blocks,
> passwords, domain names, resource specifications, etc.) MUST be confirmed with the
> user. Do NOT assume or use default values without explicit user approval.

### 1. Query Instances

List instances in a region with optional filters:

```bash
# List all instances in a region
aliyun ecs describe-instances --biz-region-id <RegionId> \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-instance-ops/{session-id}

# Query specific instance by ID
aliyun ecs describe-instances --biz-region-id <RegionId> \
  --instance-ids '["<InstanceId>"]' \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-instance-ops/{session-id}

# Filter by status (Running, Stopped, Starting, Stopping, Pending)
aliyun ecs describe-instances --biz-region-id <RegionId> \
  --status Running \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-instance-ops/{session-id}

# Filter by instance name
aliyun ecs describe-instances --biz-region-id <RegionId> \
  --instance-name "<InstanceName>" \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-instance-ops/{session-id}
```

### 2. Create and Start Instance

> **Cost estimation**: Before executing `run-instances`, run with `--estimate-cost` to get a quote. Present the cost to the user (e.g. "Estimated instance cost: ¥X/month (PostPaid) or ¥X (PrePaid). Proceed?").

```bash
# Create and start instance (RunInstances)
aliyun ecs run-instances \
  --biz-region-id <RegionId> \
  --security-group-id <SecurityGroupId> \
  --v-switch-id <VSwitchId> \
  --image-id <ImageId> \
  --instance-type <InstanceType> \
  --instance-name <InstanceName> \
  --system-disk.category cloud_essd \
  --system-disk.size 40 \
  --instance-charge-type PostPaid \
  --internet-max-bandwidth-out 0 \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-instance-ops/{session-id}
```

### 3. Start / Stop / Restart Instance

```bash
# Start instance
aliyun ecs start-instance --instance-id <InstanceId> \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-instance-ops/{session-id}

# Stop instance (graceful)
aliyun ecs stop-instance --instance-id <InstanceId> \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-instance-ops/{session-id}

# Stop instance (force)
aliyun ecs stop-instance --instance-id <InstanceId> \
  --force-stop true \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-instance-ops/{session-id}

# Restart instance
aliyun ecs reboot-instance --instance-id <InstanceId> \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-instance-ops/{session-id}
```

### 4. Release Instance

```bash
# Release a Pay-As-You-Go instance
aliyun ecs delete-instance --instance-id <InstanceId> --force true \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-instance-ops/{session-id}
```

> **WARNING:** Instance release is irreversible. Always confirm with the user before executing.

### 5. Modify Instance Attributes

> **Cost estimation**: Before executing `modify-instance-spec`, run with `--estimate-cost` to get a quote for the spec change delta. Present the cost to the user (e.g. "Estimated spec change delta: ¥X. Proceed?").

```bash
# Modify instance name
aliyun ecs modify-instance-attribute --instance-id <InstanceId> \
  --instance-name "<NewName>" \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-instance-ops/{session-id}

# Modify instance type (requires stop first)
aliyun ecs modify-instance-spec --instance-id <InstanceId> \
  --instance-type <NewInstanceType> \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-instance-ops/{session-id}
```

## RAM Policy

| Action | Resource |
|--------|----------|
| `ecs:DescribeInstances` | `*` |
| `ecs:RunInstances` | `*` |
| `ecs:StartInstance` | `acs:ecs:*:*:instance/<InstanceId>` |
| `ecs:StopInstance` | `acs:ecs:*:*:instance/<InstanceId>` |
| `ecs:RebootInstance` | `acs:ecs:*:*:instance/<InstanceId>` |
| `ecs:DeleteInstance` | `acs:ecs:*:*:instance/<InstanceId>` |
| `ecs:ModifyInstanceAttribute` | `acs:ecs:*:*:instance/<InstanceId>` |
| `ecs:ModifyInstanceSpec` | `acs:ecs:*:*:instance/<InstanceId>` |

> **[MUST] Permission Failure Handling:** When any command or API call fails due to permission errors at any point during execution, follow this process:
> 1. Read `references/ram-policies.md` to get the full list of permissions required by this SKILL
> 2. Use `ram-permission-diagnose` skill to guide the user through requesting the necessary permissions
> 3. Pause and wait until the user confirms that the required permissions have been granted

## Success Verification

```bash
# Verify instance status after operations
aliyun ecs describe-instances --biz-region-id <RegionId> \
  --instance-ids '["<InstanceId>"]' \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-instance-ops/{session-id}
# Check Status field: Running, Stopped, Starting, Stopping
```

## Related Commands Reference

See `references/related-commands.md` for the complete ECS instance CLI command reference.
