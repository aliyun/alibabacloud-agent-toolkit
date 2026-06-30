# Static Checks

Use these checks exactly when the main workflow asks for provider-block or
deprecated-field verification. Replace `<target-dir>` with the generated
Terraform project directory. Execute snippets with `bash`, not `zsh`.

## Provider Block Check

Run after HCL generation. All three checks must return `OK`.

```bash
# 1. required_providers has aliyun/alicloud with a ~> 1.<minor> version
awk '
  /required_providers[[:space:]]*{/ { in_req=1 }
  in_req && /alicloud[[:space:]]*=[[:space:]]*{/ { in_ali=1 }
  in_ali && /source[[:space:]]*=[[:space:]]*"aliyun\/alicloud"/ { source=1 }
  in_ali && /version[[:space:]]*=[[:space:]]*"~>[[:space:]]*1\.[0-9]+"/ { version=1 }
  in_ali && /^[[:space:]]*}/ { in_ali=0 }
  END { exit(source && version ? 0 : 1) }
' <target-dir>/*.tf \
  && echo OK_VERSION || echo BAD_OR_MISSING_VERSION

# 2. configuration_source attribution present somewhere
grep -RqE 'configuration_source[[:space:]]*=[[:space:]]*"AlibabaCloud-Agent-Toolkit/alibabacloud-core"' \
  <target-dir>/*.tf \
  && echo OK_CFG_SOURCE || echo MISSING_CFG_SOURCE

# 3. region uses variable, not hardcoded
grep -Rq 'region\s*=\s*var\.region' <target-dir>/*.tf \
  && echo OK_REGION_VAR || echo HARDCODED_REGION
```

## Deprecated Field Audit

Run after writing HCL and before IaCService validation. Every emitted line must
be `OK:`. Filter `deprecated-fields.md` to generated resources first; do not
walk the full table when only a few resource types were generated.

```bash
# Filter deprecated-fields.md to generated resources, then check whether any
# deprecated field that applies to those resources is still in use.
# Uses awk to extract individual resource blocks before field matching,
# so that short field names (name, document) don't falsely match
# substrings in compound field names (role_name, policy_document).
resources=$(
  grep -Rho 'resource "alicloud_[^"]*"' <target-dir>/*.tf \
    | sed -E 's/resource "([^"]+)"/\1/' \
    | sort -u \
    | paste -sd'|' -
)

if [ -n "$resources" ]; then
  pattern='\`('"$resources)"'\`'
  grep -E "$pattern" references/deprecated-fields.md
fi | while IFS='|' read _ resource field kind _; do
  resource=$(echo "$resource" | tr -d ' `')
  field=$(echo "$field" | tr -d ' `')
  kind=$(echo "$kind" | tr -d ' ')
  case "$kind" in
    rename|deprecated-no-replacement)
      awk -v res="$resource" -v fld="$field" '
        $0 ~ "resource \"" res "\"" { in_block=1; next }
        in_block && /^}/ { in_block=0 }
        in_block && $0 ~ "(^|[^_[:alnum:]])" fld "([^_[:alnum:]]|$)" { found=1; exit }
        END { exit found ? 0 : 1 }
      ' <target-dir>/*.tf \
        && echo "DEPRECATED: $resource.$field" || echo "OK: $resource.$field"
      ;;
    split|soft-split)
      awk -v res="$resource" -v fld="$field" '
        $0 ~ "resource \"" res "\"" { in_block=1; next }
        in_block && /^}/ { in_block=0 }
        in_block && $0 ~ "(^|[^_[:alnum:]])" fld "[[:space:]]*=" { found=1; exit }
        END { exit found ? 0 : 1 }
      ' <target-dir>/*.tf \
        && echo "DEPRECATED: $resource.$field (inline — use standalone sub-resource)" \
        || echo "OK: $resource.$field (not inline)"
      ;;
  esac
done
```

If any `DEPRECATED:` line appears:

1. Read each `DEPRECATED:` line; it names the resource and field.
2. Look up that resource+field in `references/deprecated-fields.md` for the
   Action column.
3. Fix the HCL.
4. Re-run this audit until every line returns `OK:`.
