# RAM permissions

Grant only the exact read action needed by the selected account query. The official page handoff does not authorize direct filing submission.

## required_permissions

- `beian:RetrieveBeianKnowledge`
- `beian:QueryBeianOrder`
- `companyreg:QuerySuccessIcpData`

The current references disagree on historical product prefixes for successful-filing queries. Treat the exact `AccessDeniedDetail.AuthAction` returned by the installed DomainCLI implementation as the compatibility signal, then update this file before claiming permission coverage. Never use wildcard actions.
