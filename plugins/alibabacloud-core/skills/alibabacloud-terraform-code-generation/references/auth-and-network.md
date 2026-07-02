# Auth and Network Reference

This skill generates and validates Terraform code; it does not consume cloud
credentials. The alicloud provider reads credentials itself from environment
variables, shared config, RAM role, OIDC/RRSA, sidecar, or static HCL.

Never emit static `access_key` / `secret_key`, and do not recommend deprecated
`ALICLOUD_*` or `ALIBABACLOUD_*` env names. Current env names are:

- `ALIBABA_CLOUD_ACCESS_KEY_ID`
- `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
- `ALIBABA_CLOUD_SECURITY_TOKEN`

If a later deployment workflow hits Terraform Registry network failures, suggest
an Alibaba Cloud mirror config for the user's Terraform CLI config file, but do
not write user-global files such as `~/.terraformrc` autonomously.
