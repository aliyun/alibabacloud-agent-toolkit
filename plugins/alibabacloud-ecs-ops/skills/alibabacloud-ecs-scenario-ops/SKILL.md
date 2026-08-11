---
name: alibabacloud-ecs-scenario-ops
description: |
  Alibaba Cloud ECS scenario-based operations. Use for end-to-end operational scenarios
  that combine multiple ECS operations into complete workflows: full-stack instance
  provisioning (VPC + SecurityGroup + Instance), disk expansion with OS resize, adding
  data disks with formatting, instance migration, and batch operations.
  Triggers: "create full instance", "provision ecs", "expand disk and resize partition",
  "add data disk", "format disk", "ecs migration", "batch ecs operations",
  "ecs scenario", "full stack ecs", "instance with network".
source: alibabacloud-ecs-ops
---

# ECS Scenario-Based Operations

End-to-end operational scenarios combining multiple ECS capabilities into complete workflows.

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
--user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-scenario-ops/{session-id}
```

## Cost Estimation (MUST before any chargeable scenario)

Every scenario below may contain chargeable operations. Before executing **step 1** of any scenario, you **MUST** follow the `alibabacloud-cli-cost-estimation` skill to evaluate the **overall task cost**:

1. **Quote all chargeable steps** up front using `--estimate-cost` and `--estimate-cost-context` as needed.
2. **Present one consolidated cost plan** with each step labelled (`PAY NOW` / `FUTURE` / `REFUND` / `FREE`), plus the total of immediate charges.
3. **Ask for a single confirmation** of the whole scenario, then execute steps in order.
4. If a step fails mid-sequence, stop and re-quote remaining steps before continuing.

> The cost evaluation output **must** include a clearly labelled cost summary section so the user can identify it before confirming.

See the `alibabacloud-cli-cost-estimation` SKILL.md for the full cost plan format and quoting rules.

## Core Workflow

> **IMPORTANT: Parameter Confirmation** — Before executing any command or API call,
> ALL user-customizable parameters MUST be confirmed with the user.

---

### Scenario 1: Full-Stack Instance Provisioning

Provision a complete ECS instance with VPC, VSwitch, Security Group, and Instance.

#### Step 1.1: Check or Create VPC

```bash
# Check existing VPCs
aliyun vpc describe-vpcs --biz-region-id <RegionId> \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-scenario-ops/{session-id}

# Create VPC if needed
aliyun vpc create-vpc --biz-region-id <RegionId> \
  --cidr-block 10.0.0.0/8 \
  --vpc-name "<VpcName>" \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-scenario-ops/{session-id}

# Wait for VPC Available
aliyun vpc describe-vpcs --biz-region-id <RegionId> \
  --vpc-id <VpcId> \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-scenario-ops/{session-id}
```

#### Step 1.2: Create VSwitch

```bash
aliyun vpc create-v-switch --biz-region-id <RegionId> \
  --zone-id <ZoneId> \
  --vpc-id <VpcId> \
  --cidr-block 10.1.1.0/24 \
  --v-switch-name "<VSwitchName>" \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-scenario-ops/{session-id}
```

#### Step 1.3: Create Security Group with Rules

```bash
# Create security group
aliyun ecs create-security-group --biz-region-id <RegionId> \
  --vpc-id <VpcId> \
  --security-group-name "<SGName>" \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-scenario-ops/{session-id}

# Add SSH access rule
aliyun ecs authorize-security-group --biz-region-id <RegionId> \
  --security-group-id <SecurityGroupId> \
  --ip-protocol tcp \
  --port-range 22/22 \
  --source-cidr-ip <SourceCIDR> \
  --policy accept \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-scenario-ops/{session-id}
```

#### Step 1.4: Create and Start Instance

```bash
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
  --internet-max-bandwidth-out 5 \
  --internet-charge-type PayByTraffic \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-scenario-ops/{session-id}
```

#### Step 1.5: Wait for Instance Running

```bash
# Poll until instance is Running
aliyun ecs describe-instances --biz-region-id <RegionId> \
  --instance-ids '["<InstanceId>"]' \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-scenario-ops/{session-id}
```

---

### Scenario 2: Disk Expansion with OS Partition Resize

Expand a cloud disk and resize the OS partition in one workflow.

#### Step 2.1: Create Snapshot (Safety Backup)

```bash
aliyun ecs create-snapshot --disk-id <DiskId> \
  --snapshot-name "pre-resize-$(date +%Y%m%d)" \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-scenario-ops/{session-id}
```

#### Step 2.2: Expand Cloud Disk

```bash
aliyun ecs resize-disk --disk-id <DiskId> \
  --new-size <NewSizeGB> \
  --type online \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-scenario-ops/{session-id}
```

#### Step 2.3: Resize OS Partition (via Cloud Assistant)

```bash
# For Linux ext4 filesystem
aliyun ecs run-command \
  --biz-region-id <RegionId> \
  --type RunShellScript \
  --command-content "$(echo 'growpart /dev/vda 1 && resize2fs /dev/vda1 && df -h' | base64)" \
  --content-encoding Base64 \
  --instance-id.1 <InstanceId> \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-scenario-ops/{session-id}

# For Linux xfs filesystem
aliyun ecs run-command \
  --biz-region-id <RegionId> \
  --type RunShellScript \
  --command-content "$(echo 'growpart /dev/vda 1 && xfs_growfs /dev/vda1 && df -h' | base64)" \
  --content-encoding Base64 \
  --instance-id.1 <InstanceId> \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-scenario-ops/{session-id}
```

---

### Scenario 3: Add and Format Data Disk

Create, attach, and format a new data disk for an existing instance.

#### Step 3.1: Create and Attach Data Disk

```bash
# Create data disk
aliyun ecs create-disk --biz-region-id <RegionId> \
  --zone-id <ZoneId> \
  --disk-category cloud_essd \
  --size <SizeGB> \
  --disk-name "<DataDiskName>" \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-scenario-ops/{session-id}

# Attach to instance
aliyun ecs attach-disk --instance-id <InstanceId> \
  --disk-id <DiskId> \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-scenario-ops/{session-id}
```

#### Step 3.2: Format and Mount (via Cloud Assistant)

```bash
# Partition, format (ext4), and mount data disk
aliyun ecs run-command \
  --biz-region-id <RegionId> \
  --type RunShellScript \
  --command-content "$(echo 'fdisk -u -c /dev/vdb <<EOF
n
p
1


w
EOF
mkfs.ext4 /dev/vdb1
mkdir -p /data
mount /dev/vdb1 /data
echo "/dev/vdb1 /data ext4 defaults 0 0" >> /etc/fstab
df -h' | base64)" \
  --content-encoding Base64 \
  --instance-id.1 <InstanceId> \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-scenario-ops/{session-id}
```

---

### Scenario 4: Batch Instance Operations

Perform operations on multiple instances simultaneously.

```bash
# Batch stop instances
for id in <InstanceId1> <InstanceId2> <InstanceId3>; do
  aliyun ecs stop-instance --instance-id "$id" \
    --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-scenario-ops/{session-id}
done

# Batch query instance status
aliyun ecs describe-instances --biz-region-id <RegionId> \
  --instance-ids '["<Id1>","<Id2>","<Id3>"]' \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-scenario-ops/{session-id}
```

## RAM Policy

Combines permissions from all involved ECS operations:
- VPC: `vpc:CreateVpc`, `vpc:CreateVSwitch`, `vpc:DescribeVpcs`, `vpc:DescribeVSwitches`
- ECS: `ecs:RunInstances`, `ecs:DescribeInstances`, `ecs:CreateSecurityGroup`, `ecs:AuthorizeSecurityGroup`
- Disk: `ecs:CreateDisk`, `ecs:AttachDisk`, `ecs:ResizeDisk`, `ecs:CreateSnapshot`
- Cloud Assistant: `ecs:RunCommand`, `ecs:DescribeInvocations`

> **[MUST] Permission Failure Handling:** When any command fails due to permission errors, read `references/ram-policies.md`, use `ram-permission-diagnose` skill, and pause until permissions are granted.

## Success Verification

- **Scenario 1**: Instance in `Running` state, SSH accessible, security group rules correct
- **Scenario 2**: Disk size matches new value, `df -h` shows expanded partition
- **Scenario 3**: Data disk visible in `lsblk`, mounted at target path, survives reboot
- **Scenario 4**: All target instances in expected state

## Cleanup

For each scenario, reverse the creation order:
1. Release/delete instances → 2. Delete disks → 3. Delete snapshots → 4. Delete security groups → 5. Delete VSwitches → 6. Delete VPCs
