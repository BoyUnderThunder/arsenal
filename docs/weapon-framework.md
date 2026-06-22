# The Weapon Framework (Armory)

Every weapon name is a shell launcher for a real tool; arguments pass straight
through. One registry file drives both the launchers and the `arsenal` table, so
they never drift.

## How it works
- **Registry:** `/usr/local/share/arsenal/registry`, pipe-delimited:
  `weapon|binary|category|description`. Lines starting with `#` are comments.
- **Launchers:** `/etc/profile.d/arsenal-armory.sh` reads the registry and
  defines one shell function per weapon at login. Calling `sniper -sV host`
  checks the binary exists, then runs `nmap -sV host`.
- **Listing:** `arsenal armory` (or bare `arsenal`) renders the registry with an
  installed indicator (`●`/`○`).

## Weapons
| Weapon | Tool | Weapon | Tool |
|---|---|---|---|
| sniper | nmap | overseer | wireshark |
| bazooka | msfconsole | hunter | bloodhound |
| tower | burpsuite | scalpel | ghidra |
| tank | hydra | detective | vol (volatility3) |
| breaker | hashcat | interrogator | autopsy |
| masterkey | sqlmap | locksmith | netexec |
| agent | aircrack-ng | pickpocket | impacket-secretsdump |
| poltergeist | responder | jackhammer | ffuf |
| excavator | feroxbuster | breach | gobuster |
| probe | nikto | blueprint | searchsploit |

## Adding a weapon
Append a line to the registry:
```
recon-x|amass|Recon|OWASP Amass — subdomain enumeration
```
It appears in `arsenal` and becomes a launcher on next login — no code change.
(In the repo, edit `profile/airootfs/usr/local/share/arsenal/registry`.)

## Notes
- A weapon whose tool isn't installed prints a clear message (exit 127); install
  it with `pacman -S <tool>` (BlackArch is enabled on the live system).
- Weapon names are chosen to avoid clashing with common commands.
