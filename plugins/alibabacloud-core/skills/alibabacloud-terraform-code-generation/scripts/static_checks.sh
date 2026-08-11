#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: scripts/static_checks.sh {provider|deprecated|all} <target-dir>" >&2
  exit 2
}

mode="${1:-}"
target="${2:-}"
[[ -n "$mode" && -n "$target" ]] || usage
[[ -d "$target" ]] || { echo "target directory not found: $target" >&2; exit 2; }

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tf_glob=("$target"/*.tf)
[[ -e "${tf_glob[0]}" ]] || { echo "no .tf files found in $target" >&2; exit 2; }

provider_check() {
  awk '
    /required_providers[[:space:]]*{/ { in_req=1 }
    in_req && /alicloud[[:space:]]*=[[:space:]]*{/ { in_ali=1 }
    in_ali && /source[[:space:]]*=[[:space:]]*"aliyun\/alicloud"/ { source=1 }
    in_ali && /version[[:space:]]*=[[:space:]]*"~>[[:space:]]*1\.[0-9]+(\.[0-9]+)?"/ { version=1 }
    in_ali && /^[[:space:]]*}/ { in_ali=0 }
    END { exit(source && version ? 0 : 1) }
  ' "${tf_glob[@]}" && echo OK_VERSION || echo BAD_OR_MISSING_VERSION

  grep -RqE 'configuration_source[[:space:]]*=[[:space:]]*"AlibabaCloud-Agent-Skills/alibabacloud-terraform-code-generation/[0-9a-fA-F]{32}"' \
    "${tf_glob[@]}" && echo OK_CFG_SOURCE || echo MISSING_CFG_SOURCE

  grep -REq 'region[[:space:]]*=[[:space:]]*var\.region' "${tf_glob[@]}" \
    && echo OK_REGION_VAR || echo HARDCODED_REGION
}

deprecated_check() {
  resources=$(
    grep -Rho 'resource "alicloud_[^"]*"' "${tf_glob[@]}" \
      | sed -E 's/resource "([^"]+)"/\1/' \
      | sort -u \
      | paste -sd'|' -
  )

  if [[ -n "$resources" ]]; then
    pattern='\`('"$resources)"'\`'
    grep -E "$pattern" "$repo_root/references/deprecated-fields.md" || true
  fi | while IFS='|' read -r _ resource field kind _; do
    resource=$(echo "$resource" | tr -d ' `')
    field=$(echo "$field" | tr -d ' `')
    kind=$(echo "$kind" | tr -d ' ')
    [[ -n "$resource" && -n "$field" && -n "$kind" ]] || continue
    case "$kind" in
      rename|deprecated-no-replacement)
        awk -v res="$resource" -v fld="$field" '
          $0 ~ "resource \"" res "\"" { in_block=1; next }
          in_block && /^}/ { in_block=0 }
          in_block && $0 ~ "(^|[^_[:alnum:]])" fld "([^_[:alnum:]]|$)" { found=1; exit }
          END { exit found ? 0 : 1 }
        ' "${tf_glob[@]}" \
          && echo "DEPRECATED: $resource.$field" || echo "OK: $resource.$field"
        ;;
      split|soft-split)
        awk -v res="$resource" -v fld="$field" '
          $0 ~ "resource \"" res "\"" { in_block=1; next }
          in_block && /^}/ { in_block=0 }
          in_block && $0 ~ "(^|[^_[:alnum:]])" fld "([[:space:]]*=|[[:space:]]*\\{)" { found=1; exit }
          END { exit found ? 0 : 1 }
        ' "${tf_glob[@]}" \
          && echo "DEPRECATED: $resource.$field (inline - use standalone sub-resource)" \
          || echo "OK: $resource.$field (not inline)"
        ;;
    esac
  done
}

case "$mode" in
  provider) provider_check ;;
  deprecated) deprecated_check ;;
  all) provider_check; deprecated_check ;;
  *) usage ;;
esac
