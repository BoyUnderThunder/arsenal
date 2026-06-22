# The Fortress (Hardening)

Arsenal ships hardened by default. Verify everything at runtime with
`arsenal doctor`.

## Kernel
- **`linux-hardened`** replaces the stock kernel (stricter defaults + exploit
  mitigations). Boot entries and the mkinitcpio preset target
  `vmlinuz-linux-hardened` / `initramfs-linux-hardened.img`.

## AppArmor
- `apparmor` package + `apparmor.service` enabled.
- Kernel cmdline: `lsm=landlock,lockdown,yama,integrity,apparmor,bpf
  apparmor=1 security=apparmor`.
- `audit` is installed for AppArmor event logging.

## Firewall (nftables, default-deny)
- `/etc/nftables.conf`: input policy **drop**; only loopback,
  established/related and ICMP allowed; forward dropped; output allowed.
- `nftables.service` enabled. No listening services are exposed by default.
- Open a port by uncommenting a rule in `/etc/nftables.conf`, then
  `systemctl reload nftables`.

## Disk encryption (LUKS-ready)
- Initramfs includes the `encrypt` + `lvm2` hooks; `cryptsetup`, `lvm2`,
  `gptfdisk` are installed — so you can boot from / install onto LUKS volumes.

## Kernel parameters (sysctl)
`/etc/sysctl.d/99-arsenal-hardening.conf` sets `kptr_restrict=2`,
`dmesg_restrict=1`, `yama.ptrace_scope=1`, reverse-path filtering,
`tcp_syncookies`, protected symlinks/hardlinks/FIFOs, restricted BPF/perf, etc.

## Module blacklist
`/etc/modprobe.d/arsenal-blacklist.conf` disables legacy/abusable modules
(dccp, sctp, rds, tipc, cramfs, hfs, firewire/thunderbolt DMA, …).

## Verifying
```bash
arsenal doctor          # [✓]/[!]/[✗] for kernel, AppArmor, firewall, …
aa-status               # AppArmor profiles
nft list ruleset        # active firewall rules
```
