# Arsenal Armory — weapon launchers for the bundled toolkit.
# Sourced for every login shell. Each weapon name launches its real tool,
# passing all arguments straight through. Driven by the registry file so the
# `arsenal` command and these launchers never drift apart.
# shellcheck shell=sh disable=SC2034

__arsenal_registry="${ARSENAL_REGISTRY:-/usr/local/share/arsenal/registry}"

if [ -r "$__arsenal_registry" ]; then
    while IFS='|' read -r __w __bin __cat __desc; do
        case "$__w" in ''|\#*) continue ;; esac
        eval "${__w}() {
            if ! command -v ${__bin} >/dev/null 2>&1; then
                printf '\033[1;31m[arsenal]\033[0m %s (%s) is not installed on this image.\n' '${__w}' '${__bin}' >&2
                return 127
            fi
            printf '\033[1;31m[arsenal]\033[0m %s \342\206\222 %s\n' '${__w}' '${__bin}' >&2
            ${__bin} \"\$@\"
        }"
    done < "$__arsenal_registry"
    unset __w __bin __cat __desc
fi
unset __arsenal_registry
