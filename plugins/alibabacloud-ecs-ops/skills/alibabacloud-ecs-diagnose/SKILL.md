---
name: alibabacloud-ecs-diagnose
description: |
  Alibaba Cloud ECS instance diagnostics and troubleshooting. Use for diagnosing instance
  connection issues, performance problems, system status checks, and health monitoring.
  Covers SSH/RDP connectivity, system events, instance health, and performance analysis.
  Triggers: "ecs diagnose", "ecs troubleshoot", "instance connection issue",
  "ssh cannot connect", "ecs performance", "instance health", "ecs monitoring",
  "system event", "instance unreachable".
source: alibabacloud-ecs-ops
---

# ECS Diagnostics and Troubleshooting

Diagnose and troubleshoot Alibaba Cloud ECS instance issues: connectivity, performance, system events, and health.

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
--user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-diagnose/{session-id}
```

## Core Workflow

> **IMPORTANT: Parameter Confirmation** — Before executing any command or API call,
> ALL user-customizable parameters MUST be confirmed with the user.

### 1. Instance Health Check

```bash
# Check instance system status (Normal, Warning, Impaired, etc.)
aliyun ecs describe-instance-status --biz-region-id <RegionId> \
  --instance-ids '["<InstanceId>"]' \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-diagnose/{session-id}

# Query instance system events (planned maintenance, unexpected events)
aliyun ecs describe-instance-history-events --biz-region-id <RegionId> \
  --instance-id <InstanceId> \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-diagnose/{session-id}

# Query instance attribute including host details
aliyun ecs describe-instance-attribute --instance-id <InstanceId> \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-diagnose/{session-id}
```

### 2. Connectivity Diagnosis

```bash
# Check instance network interfaces
aliyun ecs describe-network-interfaces --biz-region-id <RegionId> \
  --instance-id <InstanceId> \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-diagnose/{session-id}

# Check security group rules (SSH/RDP access)
aliyun ecs describe-security-group-attribute --security-group-id <SecurityGroupId> \
  --direction ingress \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-diagnose/{session-id}

# Check VPC route table
aliyun vpc describe-route-table-list --biz-region-id <RegionId> \
  --vpc-id <VpcId> \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-diagnose/{session-id}
```

### 3. Performance Monitoring via Cloud Monitor

```bash
# Query CPU utilization metrics
aliyun cms describe-metric-last --product-code ecs \
  --metric-name CPUUtilization \
  --dimensions '[{"instanceId":"<InstanceId>"}]' \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-diagnose/{session-id}

# Query memory utilization (requires Cloud Monitor agent)
aliyun cms describe-metric-last --product-code ecs \
  --metric-name memory_usedutilization \
  --dimensions '[{"instanceId":"<InstanceId>"}]' \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-diagnose/{session-id}

# Query disk IOPS
aliyun cms describe-metric-last --product-code ecs \
  --metric-name DiskReadIOPS \
  --dimensions '[{"instanceId":"<InstanceId>"}]' \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-diagnose/{session-id}
```

### 4. Cloud Assistant Remote Diagnosis

Use Cloud Assistant to run diagnostic commands on the instance without SSH:

```bash
# Run diagnostic command on Linux instance
aliyun ecs run-command \
  --biz-region-id <RegionId> \
  --type RunShellScript \
  --command-content "$(echo 'echo "=== System Uptime ===" && uptime && echo "=== Memory ===" && free -h && echo "=== Disk ===" && df -h && echo "=== Top CPU ===" && ps aux --sort=-%cpu | head -5' | base64)" \
  --content-encoding Base64 \
  --instance-id.1 <InstanceId> \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-diagnose/{session-id}

# Check command execution result
aliyun ecs describe-invocations --biz-region-id <RegionId> \
  --invoke-id <InvokeId> \
  --include-output true \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-diagnose/{session-id}
```

### 5. Diagnosis Checklist

When diagnosing connection issues, follow this order:
1. **Instance Status** — Verify instance is in `Running` state
2. **System Events** — Check for planned maintenance or unexpected events
3. **Security Group** — Verify inbound rules allow SSH (port 22) or RDP (port 3389)
4. **Network Interface** — Check ENI status and public/private IP assignment
5. **VPC/Route Table** — Verify route table has correct entries
6. **OS-level** — Use Cloud Assistant to check OS firewall, SSH daemon, etc.

## RAM Policy

| Action | Resource |
|--------|----------|
| `ecs:DescribeInstanceStatus` | `*` |
| `ecs:DescribeInstanceHistoryEvents` | `acs:ecs:*:*:instance/<InstanceId>` |
| `ecs:DescribeInstanceAttribute` | `acs:ecs:*:*:instance/<InstanceId>` |
| `ecs:DescribeNetworkInterfaces` | `*` |
| `ecs:DescribeSecurityGroupAttribute` | `acs:ecs:*:*:securitygroup/<SecurityGroupId>` |
| `ecs:RunCommand` | `acs:ecs:*:*:instance/<InstanceId>` |
| `ecs:DescribeInvocations` | `*` |
| `cms:DescribeMetricLast` | `*` |
| `vpc:DescribeRouteTableList` | `*` |

> **[MUST] Permission Failure Handling:** When any command fails due to permission errors, read `references/ram-policies.md`, use `ram-permission-diagnose` skill, and pause until permissions are granted.

## Success Verification

- Instance status shows `Running`
- No active system events with `Executing` or `Scheduled` status
- Security group allows required ports
- Cloud Monitor metrics return valid data points
