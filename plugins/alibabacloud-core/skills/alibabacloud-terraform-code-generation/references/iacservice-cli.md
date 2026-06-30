# IaCService CLI Reference

All IaCService calls are invoked through the MCP tool ending in
`AlibabaCloud___CallCLI` exposed in the current session. Do NOT shell out to
`aliyun` locally.

IaCService uses the fixed Zhangjiakou endpoint:
`--endpoint iac.cn-zhangjiakou.aliyuncs.com`.

| API | CLI Command | Purpose |
| --- | ----------- | ------- |
| ListProducts | `aliyun iacservice list-products --endpoint iac.cn-zhangjiakou.aliyuncs.com` | List Alibaba Cloud products that support Terraform |
| ListResourceTypes | `aliyun iacservice list-resource-types --product <product> --endpoint iac.cn-zhangjiakou.aliyuncs.com` | List Terraform resource types for a specific product |
| GetResourceType | `aliyun iacservice get-resource-type --resource-type <resourceType> --endpoint iac.cn-zhangjiakou.aliyuncs.com` | Get Terraform resource schema and attributes |
| ListResourceTypeExamples | `aliyun iacservice list-resource-type-examples --resource-type <resourceType> --endpoint iac.cn-zhangjiakou.aliyuncs.com` | List official Terraform examples for a resource type |
| GetResourceTypeExample | `aliyun iacservice get-resource-type-example --example-id <exampleId> --endpoint iac.cn-zhangjiakou.aliyuncs.com` | Fetch official example Terraform code |
| GetProviderDocument | `aliyun iacservice get-provider-document --resource-type <resourceType> --endpoint iac.cn-zhangjiakou.aliyuncs.com` | Fetch provider documentation |
| ListTerraformProviderVersions | `aliyun iacservice list-terraform-provider-versions --endpoint iac.cn-zhangjiakou.aliyuncs.com` | List published `aliyun/alicloud` provider versions |
| ValidateModule | `aliyun iacservice validate-module --source Upload --code <combined-hcl> --endpoint iac.cn-zhangjiakou.aliyuncs.com` or `--code-map '{<file>: <hcl>, ...}'` | Validate Terraform syntax and schema server-side |

## validate-module Parameters

| Param | Type | Notes |
| --- | --- | --- |
| `--client-token` | string `[0-9a-zA-Z-]{1,64}` | Idempotency key, UUID recommended |
| `--code` | string | Fast path. Use a single file's HCL, or concatenate generated `.tf` files in memory for validation. MUST preserve real newlines; do not collapse HCL to one line. |
| `--code-map` | JSON string `{<filename>: <hcl>, ...}` | Slower path. Use only when filename-specific diagnostics are needed or `--code` fails unexpectedly. |
| `--source` | enum | Use `Upload` for inline text |
| `--source-path` | string | Source path for other source types |
