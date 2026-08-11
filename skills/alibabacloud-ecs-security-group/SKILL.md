---
name: alibabacloud-ecs-security-group
description: |
  Alibaba Cloud ECS security group and network management. Use for creating and managing
  security groups, configuring inbound/outbound rules, managing network interfaces, and
  troubleshooting network connectivity. Covers security group CRUD, rule management,
  ENI operations, and VPC network checks.
  Triggers: "security group", "ecs network", "firewall rule", "security group rule",
  "inbound rule", "outbound rule", "network interface", "ENI", "port access",
  "open port", "security group management".
source: alibabacloud-ecs-ops
---

# ECS Security Group and Network Management

Manage security groups and network configurations for Alibaba Cloud ECS instances.

> **Pre-check: Alibaba Cloud CLI must be installed and at least version 3.3.3.**

```bash
aliyun version   # must be >= 3.3.3
```

> **Pre-check: Alibaba Cloud Credentials Required**
> ```bash
aliyun configure list
```
> If no valid profile exists, STOP and guide user to configure credentials.

> **Pre-check: Aliyun CLI plugin update required**
> ```bash
> aliyun configure set --auto-plugin-install true
> aliyun plugin update
> ```

## Observability (MUST follow for every aliyun command)

Upon loading this skill, generate a random session ID (32-char lowercase hex string) once for the entire session.

```
--user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-security-group/{session-id}
```

## Core Workflow

> **IMPORTANT: Parameter Confirmation** — Before executing any command or API call,
> ALL user-customizable parameters MUST be confirmed with the user.

### 1. Security Group Management

```bash
# List security groups in a VPC
aliyun ecs describe-security-groups --biz-region-id <RegionId> \
  --vpc-id <VpcId> \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-security-group/{session-id}

# Create security group
aliyun ecs create-security-group --biz-region-id <RegionId> \
  --vpc-id <VpcId> \
  --security-group-name "<GroupName>" \
  --security-group-type normal \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-security-group/{session-id}

# Delete security group (must have no instances)
aliyun ecs delete-security-group --biz-region-id <RegionId> \
  --security-group-id <SecurityGroupId> \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-security-group/{session-id}
```

### 2. Security Group Rules

```bash
# View security group rules
aliyun ecs describe-security-group-attribute --security-group-id <SecurityGroupId> \
  --direction ingress \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-security-group/{session-id}

# Add inbound rule (e.g., allow SSH from specific CIDR)
aliyun ecs authorize-security-group --biz-region-id <RegionId> \
  --security-group-id <SecurityGroupId> \
  --ip-protocol tcp \
  --port-range 22/22 \
  --source-cidr-ip <SourceCIDR> \
  --policy accept \
  --priority 1 \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-security-group/{session-id}

# Add outbound rule
aliyun ecs authorize-security-group-egress --biz-region-id <RegionId> \
  --security-group-id <SecurityGroupId> \
  --ip-protocol tcp \
  --port-range 443/443 \
  --dest-cidr-ip <DestCIDR> \
  --policy accept \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-security-group/{session-id}

# Revoke inbound rule
aliyun ecs revoke-security-group --biz-region-id <RegionId> \
  --security-group-id <SecurityGroupId> \
  --ip-protocol tcp \
  --port-range 22/22 \
  --source-cidr-ip <SourceCIDR> \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-security-group/{session-id}
```

### 3. Instance-Security Group Association

```bash
# Join instance to security group
aliyun ecs join-security-group --instance-id <InstanceId> \
  --security-group-id <SecurityGroupId> \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-security-group/{session-id}

# Leave security group
aliyun ecs leave-security-group --instance-id <InstanceId> \
  --security-group-id <SecurityGroupId> \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-security-group/{session-id}
```

### 4. Network Interface (ENI) Management

```bash
# List network interfaces
aliyun ecs describe-network-interfaces --biz-region-id <RegionId> \
  --instance-id <InstanceId> \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-security-group/{session-id}

# Create and attach secondary ENI
aliyun ecs create-network-interface --biz-region-id <RegionId> \
  --v-switch-id <VSwitchId> \
  --security-group-id <SecurityGroupId> \
  --network-interface-name "<ENIName>" \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-security-group/{session-id}

aliyun ecs attach-network-interface --instance-id <InstanceId> \
  --network-interface-id <ENIId> \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-security-group/{session-id}
```

### 5. VPC Network Verification

```bash
# Check VPC and VSwitch status
aliyun vpc describe-vpcs --biz-region-id <RegionId> \
  --vpc-id <VpcId> \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-security-group/{session-id}

aliyun vpc describe-v-switches --biz-region-id <RegionId> \
  --vpc-id <VpcId> \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-security-group/{session-id}

# Check route table
aliyun vpc describe-route-table-list --biz-region-id <RegionId> \
  --vpc-id <VpcId> \
  --user-agent AlibabaCloud-Agent-Skills/alibabacloud-ecs-security-group/{session-id}
```

## RAM Policy

| Action | Resource |
|--------|----------|
| `ecs:DescribeSecurityGroups` | `*` |
| `ecs:CreateSecurityGroup` | `*` |
| `ecs:DeleteSecurityGroup` | `acs:ecs:*:*:securitygroup/<SecurityGroupId>` |
| `ecs:DescribeSecurityGroupAttribute` | `acs:ecs:*:*:securitygroup/<SecurityGroupId>` |
| `ecs:AuthorizeSecurityGroup` | `acs:ecs:*:*:securitygroup/<SecurityGroupId>` |
| `ecs:AuthorizeSecurityGroupEgress` | `acs:ecs:*:*:securitygroup/<SecurityGroupId>` |
| `ecs:RevokeSecurityGroup` | `acs:ecs:*:*:securitygroup/<SecurityGroupId>` |
| `ecs:JoinSecurityGroup` | `acs:ecs:*:*:instance/<InstanceId>` |
| `ecs:LeaveSecurityGroup` | `acs:ecs:*:*:instance/<InstanceId>` |
| `ecs:DescribeNetworkInterfaces` | `*` |
| `ecs:CreateNetworkInterface` | `*` |
| `ecs:AttachNetworkInterface` | `acs:ecs:*:*:instance/<InstanceId>` |
| `vpc:DescribeVpcs` | `*` |
| `vpc:DescribeVSwitches` | `*` |
| `vpc:DescribeRouteTableList` | `*` |

> **[MUST] Permission Failure Handling:** When any command fails due to permission errors, read `references/ram-policies.md`, use `ram-permission-diagnose` skill, and pause until permissions are granted.

## Best Practices

1. **Least Privilege** — Only open required ports; avoid `0.0.0.0/0` as source CIDR
2. **Separate Groups** — Use different security groups for different application tiers
3. **Audit Regularly** — Periodically review security group rules for unnecessary access
4. **Use CIDR Blocks** — Restrict source IPs to known ranges rather than `0.0.0.0/0`
