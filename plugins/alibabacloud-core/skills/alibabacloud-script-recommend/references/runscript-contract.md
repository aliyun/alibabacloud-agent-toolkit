# RunScript Contract Reference

Read this only when validation fails repeatedly or the script needs more examples.

## Sandbox Rules

### Module Whitelist

Only these modules may be imported (both at static analysis and runtime):
`asyncio`, `collections`, `csv`, `dataclasses`, `datetime`, `decimal`, `enum`, `fractions`,
`functools`, `itertools`, `json`, `math`, `re`, `statistics`, `string`, `time`, `typing`, `uuid`.

At runtime, modules are wrapped with restricted exports; dunder attributes are inaccessible.

✅ `import json`, `from collections import defaultdict`
❌ `import os`, `import subprocess`, `import requests`, `from . import helper`

### No Reflection or Dynamic Code Execution

Forbidden: `eval`, `exec`, `compile`, `__builtins__`, `__import__`, `getattr`, `setattr`,
`hasattr`, `delattr`, `globals`, `locals`, `vars`, dynamic 3-arg `type()`.
Forbidden: dunder attributes (`__class__`, `__mro__`, `__globals__`, `__code__`, etc.)
and frame attributes (`f_builtins`, `f_globals`).
Forbidden: `importlib.import_module()`, base64/codecs/zlib decode chains used to hide code.

Dangerous builtins are unavailable at runtime: `open`, `exec`, `eval`, `__import__`, `input`, `breakpoint`.

### No Attribute Chain Escape

Accessing sensitive modules via attribute chains on allowed modules is forbidden.

✅ `import uuid; uuid.uuid4()`
❌ `import uuid; uuid.os.system('rm -rf /')`

### No OS/Subprocess/Network

Forbidden: `os.system()`, `os.popen()`, `subprocess.*`, `socket.*`, `urllib.request.urlopen()`.
File I/O (`open()` for write) outside `/tmp` is forbidden.

### No Excessive Sleep

`time.sleep()` > 30 seconds is forbidden.

### Only call_cli() for OpenAPI

Scripts must use `call_cli(product, version, action, params)`. Direct SDK instantiation
(`AcsClient`, V2 SDK), direct HTTP requests, and subprocess calls to `aliyun` CLI are forbidden.

✅ `result = call_cli(product='Ecs', version='2014-05-26', action='DescribeInstances', params={'RegionId': 'cn-hangzhou'})`
❌ `from alibabacloud_ecs20140526.client import Client`

### Blocked High-Risk Read APIs

APIs returning credentials or secrets are blocked even if read-only:
`ram.ListAccessKeys`, `sts.AssumeRole`, `kms.GetSecretValue`, `ecs.DescribeUserData`.

### Forbidden CLI Meta Products

`configure`, `plugin`, `ossutil`, `autocompletion`, etc. cannot be used as `product` argument.

### Write Operations Allowed

Write/delete/update calls execute normally via `call_cli()`. The RunScript runtime intercepts
write operations and presents them to the user for approval (HITL) before execution. The script
itself should NOT add confirmation prompts (`input()`, etc.) — the runtime handles this.

### Output via result Variable

Assign final data to `result` (dict or list). No `print()`, no file writes outside `/tmp`.

## Additional Patterns

**Create/Update with placeholders** (when user omits required values):

```python
bucket = "<bucket-name>"
result = await call_cli(product="Oss", action="PutBucket", version="2019-05-17",
    region=region_id, params={"bucket": bucket, "body": {"CreateBucketConfiguration": {"StorageClass": "Standard"}}})
```

**Multi-region parallel with error handling:**

```python
region_ids = ["cn-hangzhou", "cn-shanghai", "cn-beijing"]
responses = await asyncio.gather(*[
    call_cli(product="Ecs", action="DescribeInstances", params={"RegionId": rid, "PageSize": 100})
    for rid in region_ids
], return_exceptions=True)
result = {}
for rid, resp in zip(region_ids, responses):
    if isinstance(resp, dict):
        result[rid] = resp.get("Instances", {}).get("Instance", [])
    else:
        result[rid] = {"error": str(resp)}
```

## Remote Validation API

`POST VALIDATE_ENDPOINT_PLACEHOLDER/api/script-recommend/validate`

Headers: `Content-Type: application/json`, `User-Agent: AlibabaCloud-Agent-Skills/alibabacloud-script-recommend`

Body: `{"source": "..."}`

Response on failure:

```json
{
  "passed": false,
  "violations": [
    {"rule_id": "SEC-4001", "line": 1, "message": "Forbidden import: os", "snippet": "import os"}
  ]
}
```
