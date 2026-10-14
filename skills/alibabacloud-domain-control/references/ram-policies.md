# RAM permissions

Grant only actions required by the selected DomainCLI route. Never use product-wide wildcards.

## required_permissions

### Asset, audit, and task reads

- `domain:QueryDomainList`
- `domain:QueryDomainByDomainName`
- `domain:QueryAdvancedDomainList`
- `domain:QueryDomainGroupList`
- `domain:QueryChangeLogList`
- `domain:QueryTaskList`
- `domain:QueryTaskDetailList`
- `domain:QueryTaskInfoHistory`
- `domain:QueryTaskDetailHistory`
- `domain:PollTaskResult`

### Organization and identity

- `domain:SaveBatchDomainRemark`
- `domain:SaveDomainGroup`
- `domain:DeleteDomainGroup`
- `domain:UpdateDomainToDomainGroup`
- `domain:QueryContactInfo`
- `domain:QueryRegistrantProfiles`
- `domain:QueryRegistrantProfileRealNameVerificationInfo`
- `domain:QueryDomainRealNameVerificationInfo`
- `domain:SaveBatchTaskForUpdatingContactInfoByRegistrantProfileId`
- `domain:SaveRegistrantProfile`
- `domain:DeleteRegistrantProfile`
- `domain:SetDefaultRegistrantProfile`
- `domain:RegistrantProfileRealNameVerification`
- `domain:VerifyContactField`
- `domain:QueryDomainAdminDivision`
- `domain:QueryEmailVerification`
- `domain:ListEmailVerification`
- `domain:SubmitEmailVerification`
- `domain:ResendEmailVerification`
- `domain:DeleteEmailVerification`
- `domain:VerifyEmail`

### Alibaba Cloud DNS records

- `alidns:DescribeDomainRecords`
- `alidns:DescribeDomainRecordInfo`
- `alidns:DescribeSupportLines`
- `alidns:DescribeRecordLogs`
- `alidns:AddDomainRecord`
- `alidns:UpdateDomainRecord`
- `alidns:DeleteDomainRecord`
- `alidns:SetDomainRecordStatus`

### Registry DNS and delegation

- `domain:QueryDnsHost`
- `domain:SaveSingleTaskForCreatingDnsHost`
- `domain:SaveSingleTaskForModifyingDnsHost`
- `domain:SaveSingleTaskForDeletingDnsHost`
- `domain:QueryDSRecord`
- `domain:SaveSingleTaskForAddingDSRecord`
- `domain:SaveSingleTaskForModifyingDSRecord`
- `domain:SaveSingleTaskForDeletingDSRecord`
- `domain:SaveBatchTaskForModifyingDomainDns`

### Transfer-out and locks

- `domain:QueryTransferOutInfo`
- `domain:SaveSingleTaskForQueryingTransferAuthorizationCode`
- `domain:SaveBatchTaskForApplyQuickTransferOutOpenly`
- `domain:SaveBatchTaskForTransferProhibitionLock`
- `domain:SaveBatchTaskForUpdateProhibitionLock`
- `domain:ListServerLock`
- `domain:QueryServerLock`
- `domain:CheckProcessingServerLockApply`
- `domain:CheckMaxYearOfServerLock`

No registration, renewal, redemption, transfer-in, or marketplace funding action is permitted here. Reconcile any different exact `AccessDeniedDetail.AuthAction` before updating this list.
