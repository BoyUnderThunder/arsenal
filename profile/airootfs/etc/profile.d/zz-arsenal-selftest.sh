# shellcheck shell=sh
# Arsenal CI hardening self-test trigger.
#
# Sourced for login shells (like the armory launchers). Runs the self-test ONLY
# when the kernel was booted with the `arsenalselftest` token, which is set only
# by tools/integration-test.sh. On normal boots the token is absent and this is
# completely inert. A dot-free token is used on purpose: the kernel treats a
# dotted `name.param` token as a module parameter and does not surface it in
# /proc/cmdline.
__arsenal_cmdline="$(cat /proc/cmdline 2>/dev/null)"

# Diagnostic on the serial console only (where the CI test runs); silent on
# normal TTY/SSH logins.
case "$(tty 2>/dev/null)" in
    /dev/ttyS*) printf '[arsenal-selftest-hook] cmdline=%s\n' "${__arsenal_cmdline}" ;;
esac

case " ${__arsenal_cmdline} " in
    *" arsenalselftest "*)
        # Run via bash so a dropped exec bit can't break the CI trigger; the
        # serial sentinel (ARSENAL-SELFTEST: PASS/FAIL), not the exit code,
        # decides the result.
        bash /usr/local/bin/arsenal-selftest || true
        ;;
esac
unset __arsenal_cmdline
