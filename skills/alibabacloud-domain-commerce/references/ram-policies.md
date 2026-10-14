# RAM permissions

Grant only actions required by the selected DomainCLI route. This file is a planning aid and never authorizes the agent to modify RAM policies.

## required_permissions

### Financial and order actions

- `bssapi:QueryAccountBalance`
- `domain:SaveBatchTaskForCreatingOrderActivate`
- `domain:SaveBatchTaskForCreatingOrderRenew`
- `domain:SetupDomainAutoRenew`

### Transfer-in actions

- `domain:CheckTransferInFeasibility`
- `domain:SaveBatchTaskForCreatingOrderTransfer`
- `domain:QueryTransferInList`
- `domain:QueryTransferInByInstanceId`

### Marketplace actions

- `domain:CheckSelectedDomainStatus`
- `domain:SendAuthCode`
- `domain:PublishSelectedDomain`

### Task verification actions

- `domain:QueryTaskList`
- `domain:QueryTaskDetailList`
- `domain:QueryTaskInfoHistory`
- `domain:QueryTaskDetailHistory`
- `domain:PollTaskResult`

No transfer-out or lock action is permitted by this Skill. If the service reports a different exact `AccessDeniedDetail.AuthAction`, update this list before claiming complete coverage. Never use wildcard actions.
