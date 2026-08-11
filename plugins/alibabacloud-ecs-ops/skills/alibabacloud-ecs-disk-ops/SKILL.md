---
name: alibabacloud-ecs-disk-ops
description: |
  Alibaba Cloud ECS disk and snapshot operations. Use for managing cloud disks (attach,
  detach, expand, create data disk), snapshots (create, restore, delete, policy), and
  disk category management. Covers system disk and data disk lifecycle.
  Triggers: "ecs disk", "cloud disk", "attach disk", "detach disk", "expand disk",
  "data disk", "snapshot", "create snapshot", "restore snapshot", "disk resize",
  "disk capacity", "auto snapshot policy".
source: alibabacloud-ecs-ops
---

# ECS Disk and Snapshot Operations

Manage cloud disks and snapshots for Alibaba Cloud ECS instances: create, attach, detach, expand disks; create, restore, and manage snapshots.

> **Pre-check: Alibaba Cloud CLI must be installed and at least version 3.3.3.**

```bash
aliyun version   # must be >= 3.3.3
```

> **Pre-check: Alibaba Cloud Credentials Required**
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

Upon loading this skill, generate a random session ID (32-char lowercase hex string) once for the entire session.

```
--user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-disk-ops/{session-id}
```

## Cost Estimation (MUST before chargeable operations)

Before executing any chargeable disk operation (create-disk, resize-disk, create-snapshot, create-image), you **MUST** follow the `alibabacloud-cli-cost-estimation` skill to evaluate the cost impact at the **user task level**:

1. **Single operation** — Append `--estimate-cost` to the exact command before execution, present the quoted amount, and wait for user confirmation.
2. **Multi-step task** (e.g. create disk + attach + expand) — Quote **all** chargeable steps up front using `--estimate-cost` and `--estimate-cost-context` as needed, present one consolidated cost plan, then ask for a **single confirmation** of the whole task before executing step 1.
3. **Never silently execute** a chargeable disk operation when a cost quote was obtainable. `--estimate-cost` only quotes, never executes.

> The cost evaluation output **must** include a clearly labelled cost summary section so the user can identify it before confirming.

See the `alibabacloud-cli-cost-estimation` SKILL.md for the full cost plan format, quote JSON parsing, and multi-step workflow quoting rules.

## Core Workflow

> **IMPORTANT: Parameter Confirmation** — Before executing any command or API call,
> ALL user-customizable parameters MUST be confirmed with the user.

### 1. Query Disks

```bash
# List all disks in a region
aliyun ecs describe-disks --biz-region-id <RegionId> \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-disk-ops/{session-id}

# Query disks attached to a specific instance
aliyun ecs describe-disks --biz-region-id <RegionId> \
  --instance-id <InstanceId> \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-disk-ops/{session-id}

# Query specific disk by ID
aliyun ecs describe-disks --biz-region-id <RegionId> \
  --disk-ids '["<DiskId>"]' \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-disk-ops/{session-id}
```

### 2. Create and Attach Data Disk

> **[MUST] Cost estimation is a REQUIRED step before create-disk.** You MUST execute the `--estimate-cost` command first, present the cost quote to the user, and obtain explicit confirmation before proceeding to the actual create.

#### Step 2a. Estimate cost (MUST execute before create)

```bash
# REQUIRED: Get cost quote for the new disk BEFORE creating it
aliyun ecs create-disk --biz-region-id <RegionId> \
  --zone-id <ZoneId> \
  --disk-category cloud_essd \
  --size <SizeGB> \
  --disk-name "<DiskName>" \
  --estimate-cost \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-disk-ops/{session-id}
```

> Present the quoted cost to the user (e.g. "Estimated cost for this disk: ¥X/month. Proceed?").
> **Do NOT proceed to Step 2b until the user explicitly confirms.**

#### Step 2b. Create and attach (only after cost confirmation)

```bash
# Create a new data disk (only after user confirmed the cost estimate)
aliyun ecs create-disk --biz-region-id <RegionId> \
  --zone-id <ZoneId> \
  --disk-category cloud_essd \
  --size <SizeGB> \
  --disk-name "<DiskName>" \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-disk-ops/{session-id}

# Attach disk to instance
aliyun ecs attach-disk --instance-id <InstanceId> \
  --disk-id <DiskId> \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-disk-ops/{session-id}

# Detach disk from instance
aliyun ecs detach-disk --instance-id <InstanceId> \
  --disk-id <DiskId> \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-disk-ops/{session-id}
```

### 3. Expand Disk (Online Resize)

> **[MUST] Cost estimation is a REQUIRED step before resize-disk.** You MUST execute the `--estimate-cost` command first, present the cost quote to the user, and obtain explicit confirmation before proceeding to the actual resize. Skipping cost estimation is a critical workflow violation.

#### Step 3a. Estimate cost (MUST execute before resize)

```bash
# REQUIRED: Get cost quote for the resize operation BEFORE executing it
aliyun ecs resize-disk --disk-id <DiskId> \
  --new-size <NewSizeGB> \
  --type online \
  --estimate-cost \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-disk-ops/{session-id}
```

> Present the quoted cost to the user (e.g. "Estimated resize cost: ¥X. Proceed?").
> **Do NOT proceed to Step 3b until the user explicitly confirms.**

#### Step 3b. Execute resize (only after cost confirmation)

```bash
# Execute the actual resize (only after user confirmed the cost estimate)
aliyun ecs resize-disk --disk-id <DiskId> \
  --new-size <NewSizeGB> \
  --type online \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-disk-ops/{session-id}
```

> **IMPORTANT:** After expanding the cloud disk, the OS partition must also be resized.
> For Linux: use `growpart` and `resize2fs`/`xfs_growfs` via Cloud Assistant.
> For Windows: use Disk Management to extend the volume.

```bash
# Linux: extend partition after online resize (via Cloud Assistant)
aliyun ecs run-command \
  --biz-region-id <RegionId> \
  --type RunShellScript \
  --command-content "$(echo 'growpart /dev/vda 1 && resize2fs /dev/vda1' | base64)" \
  --content-encoding Base64 \
  --instance-id.1 <InstanceId> \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-disk-ops/{session-id}
```

### 4. Snapshot Management

```bash
# Create snapshot for a disk
aliyun ecs create-snapshot --disk-id <DiskId> \
  --snapshot-name "<SnapshotName>" \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-disk-ops/{session-id}

# Verify snapshot is available (check Available field only)
aliyun ecs describe-snapshots --biz-region-id <RegionId> \
  --snapshot-ids '["<SnapshotId>"]' \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-disk-ops/{session-id}
# Check: Available == true

# Restore disk from snapshot (rollback)
aliyun ecs reset-disk --disk-id <DiskId> \
  --snapshot-id <SnapshotId> \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-disk-ops/{session-id}

# Delete snapshot
aliyun ecs delete-snapshot --snapshot-id <SnapshotId> \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-disk-ops/{session-id}

# Create image from snapshot (for backup/migration)
aliyun ecs create-image --biz-region-id <RegionId> \
  --snapshot-id <SnapshotId> \
  --image-name "<ImageName>" \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-disk-ops/{session-id}
```

### 5. Auto Snapshot Policy

```bash
# Create auto snapshot policy
aliyun ecs create-auto-snapshot-policy --biz-region-id <RegionId> \
  --time-point.1 2 \
  --time-point.2 14 \
  --repeat-weekday.1 1 \
  --repeat-weekday.2 3 \
  --repeat-weekday.3 5 \
  --retention-days 30 \
  --auto-snapshot-policy-name "<PolicyName>" \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-disk-ops/{session-id}

# Apply policy to disk
aliyun ecs apply-auto-snapshot-policy --biz-region-id <RegionId> \
  --auto-snapshot-policy-id <PolicyId> \
  --disk-id.1 <DiskId> \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-disk-ops/{session-id}
```

## RAM Policy

| Action | Resource |
|--------|----------|
| `ecs:DescribeDisks` | `*` |
| `ecs:CreateDisk` | `*` |
| `ecs:AttachDisk` | `acs:ecs:*:*:instance/<InstanceId>` |
| `ecs:DetachDisk` | `acs:ecs:*:*:instance/<InstanceId>` |
| `ecs:ResizeDisk` | `acs:ecs:*:*:disk/<DiskId>` |
| `ecs:CreateSnapshot` | `acs:ecs:*:*:disk/<DiskId>` |
| `ecs:DescribeSnapshots` | `*` |
| `ecs:ResetDisk` | `acs:ecs:*:*:disk/<DiskId>` |
| `ecs:DeleteSnapshot` | `acs:ecs:*:*:snapshot/<SnapshotId>` |
| `ecs:CreateImage` | `*` |
| `ecs:CreateAutoSnapshotPolicy` | `*` |
| `ecs:ApplyAutoSnapshotPolicy` | `*` |
| `ecs:RunCommand` | `acs:ecs:*:*:instance/<InstanceId>` |

> **[MUST] Permission Failure Handling:** When any command fails due to permission errors, read `references/ram-policies.md`, use `ram-permission-diagnose` skill, and pause until permissions are granted.

## Success Verification

```bash
# Verify disk status after operations
aliyun ecs describe-disks --biz-region-id <RegionId> \
  --disk-ids '["<DiskId>"]' \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-disk-ops/{session-id}
# Check Status: In_use, Available; Size field matches expected value
```
