# RAM permissions

Grant only actions required by the selected Wanxiaozhi DomainCLI route. Never use wildcard actions.

## required_permissions

### Read actions

- `websitebuild:QueryInspirationBalance`
- `websitebuild:ListAppInstances`
- `websitebuild:ListAIStaffChatMessages`
- `websitebuild:GetAppWorkspaceDirectory`
- `websitebuild:GetAppFileContent`
- `websitebuild:GetAppPublishStatus`
- `websitebuild:ListAppPublishHistory`
- `websitebuild:GetAIStaffPreviewUrl`
- `websitebuild:ListAppConversations`
- `websitebuild:GetAppConversation`
- `websitebuild:GetAppConversationLockStatus`
- `websitebuild:ListAppInstanceDomains`
- `websitebuild:DescribeAppDomainDnsRecord`
- `websitebuild:ListAppDomainRedirectRecords`
- `websitebuild:QueryMaterialDirectoryTree`
- `websitebuild:QueryMaterialFileList`
- `websitebuild:QueryMaterialFileDetail`
- `websitebuild:QueryMaterialFileSummaryInfo`
- `websitebuild:ListAppPluginFiles`
- `websitebuild:ListAppPlugins`
- `websitebuild:ListMyAppPlugins`
- `websitebuild:ListMarketplaceAppPlugins`
- `websitebuild:GetAppPlugin`
- `websitebuild:ListAppPluginVersions`
- `websitebuild:CreateAppAssistantAgentSsoLogin`

### Write actions

- `websitebuild:CreateAppChat`
- `websitebuild:ReconnectAppChat`
- `websitebuild:SaveArticleDraft`
- `websitebuild:SaveImageDraft`
- `websitebuild:SaveVideoDraft`
- `websitebuild:BindAppDomain`
- `websitebuild:DeleteAppDomainRedirect`
- `websitebuild:SetAppDomainCertificate`
- `websitebuild:DeleteAppDomainCertificate`
- `websitebuild:UnbindAppDomain`
- `websitebuild:UpdateAppInstanceDomain`
- `websitebuild:CreateMaterialDirectory`
- `websitebuild:DeleteMaterialDirectory`
- `websitebuild:ExportMaterialFile`
- `websitebuild:ModifyMaterialDirectory`
- `websitebuild:ModifyMaterialFile`
- `websitebuild:ModifyMaterialFileStatus`
- `websitebuild:MoveMaterialDirectory`
- `websitebuild:MoveMaterialFile`
- `websitebuild:UploadMaterialFile`
- `websitebuild:DeleteAppInstance`
- `websitebuild:OfflineAppInstance`
- `websitebuild:OnlineAppInstance`
- `websitebuild:PublishAppInstance`
- `websitebuild:RollbackAppCodeSnapshot`
- `websitebuild:RollbackAppInstancePublish`
- `websitebuild:CreateAppPlugin`
- `websitebuild:DeleteAppPlugin`
- `websitebuild:InstallAppPlugin`
- `websitebuild:RollbackAppPluginVersion`
- `websitebuild:UninstallAppPlugin`
- `websitebuild:UpdateAppPlugin`
- `websitebuild:UploadAppPluginVersion`

Historical implementations may return legacy action prefixes. Reconcile the exact live `AccessDeniedDetail.AuthAction` before changing this list or claiming complete permission coverage.
