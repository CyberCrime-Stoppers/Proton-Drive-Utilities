# Security Policy — Proton Drive Utility App (PDUA)

**Maintainer:** Linus (CyberCrime-Stoppers / CCS)
**App version:** 1.2.10
**License:** As per repository LICENSE file

PDUA is an **unofficial** community client for Proton Drive. It is not affiliated
with, endorsed by, or audited by Proton AG. All authentication is delegated to
the official `proton-drive` CLI binary — PDUA never handles your Proton password
or receives OAuth tokens itself.

---

## 1. Supported Versions

| Version | Supported |
|---------|-----------|
| 1.2.10 (beta-releases/fixes-v1210) | ✅ Active development |
| < 1.2.10 | ❌ Upgrade required — contains known security issues (see §3) |

Security fixes are only issued for the latest beta branch.

---

## 2. Reporting a Vulnerability

**Do not open public GitHub issues for security reports.**

1. Contact the maintainer privately via GitHub Security Advisories
   ("Report a vulnerability" on the Security tab), **or**
2. Email the maintainer at the address listed on the GitHub profile.

Please include:

- Affected version and platform
- Reproduction steps or proof-of-concept
- Impact assessment

You will receive acknowledgement within **7 days**. PDUA is maintained by a
single developer in spare time; complex fixes may take longer. Credit is given
in the advisory unless you prefer to remain anonymous.

**Scope of reports accepted:** PDUA's Python/GTK code, bundled shell scripts,
and configuration handling. Issues in the Proton Drive CLI itself belong
upstream with Proton AG.

---

## 3. Past Security Issues (Resolved)

Documented for transparency. Users of affected versions should upgrade
immediately.

### SEC-001 — Plaintext passcode stored in configuration file
- **Severity:** High
- **Affected versions:** ≤ 1.2.0
- **Issue:** An early configuration scheme wrote a user-supplied "passcode"
  value in cleartext to a local JSON config file under `~/.config/`.
- **Impact:** Any process or user able to read the home directory config could
  recover the value.
- **Fix:** The passcode field was **removed entirely** from the config schema;
  the key was renamed to `username` and no secret material is ever written by
  PDUA. Authentication is performed exclusively by the official
  `proton-drive auth login` flow, which stores session credentials in the
  system keyring (GNOME Keyring / KWallet), never in PDUA's files.
- **Migration note:** Legacy config files containing the old key are migrated
  on first launch and the stale field is discarded.

### SEC-002 — Shell scripts executed without integrity verification
- **Severity:** High
- **Affected versions:** ≤ 1.2.0
- **Issue:** Transfer pages (upload/download) invoked shell scripts by path
  without verifying their contents, allowing script substitution (e.g. via a
  writable PATH entry or sibling-directory tampering).
- **Fix:** Introduced `script_guard.py`, which enforces **SHA-256 pinning**:
  every script executed by a transfer page must match a pinned hash registered
  in code. Scripts with unpopulated/placeholder hashes are refused with a clear
  error rather than executed. The 10 per-flow scripts were consolidated into
  one parameterized script (`scripts/unified/proton-transfer.sh`), shrinking
  the trusted surface by an order of magnitude.
- **Residual consideration:** Pin hashes must be regenerated when scripts are
  legitimately modified (documented in the README).

### SEC-003 — Fragmented configuration across three locations
- **Severity:** Low (defense-in-depth failure)
- **Affected versions:** ≤ 1.2.0
- **Issue:** Application state was spread across three separate locations
  (two hidden directories plus hardcoded paths), making it impractical to
  audit or permission-protect all copies.
- **Fix:** Unified to a single `~/.config/pdua/config.json` with automatic
  one-way migration of legacy files. Recommended practice: ensure the file is
  only readable by the owner (`chmod 600`); the directory is created with
  restrictive permissions where the platform supports it.

### Known non-issues / design decisions

- **Thumbnail cache** stores only scaled-down derivatives (not originals) at
  `~/.cache/pdua/thumbnails/`, keyed by SHA-256 hashes rather than original
  filenames, and evicts least-recently-used entries beyond a size budget.
  Temporary full-resolution downloads for thumbnail generation are deleted
  immediately after scaling. Users who do not want local thumbnail caches can
  disable the feature in settings.
- **No telemetry.** PDUA makes no network requests of its own; the only network
  traffic is that of the official Proton Drive CLI you configure.

---

## 4. Threat Model

| Asset | Threat | Mitigation |
|-------|--------|------------|
| Proton session credentials | Theft from PDUA | PDUA never stores them; keyring-managed by the official CLI |
| Executed scripts | Tampering/substitution | SHA-256 pinning (SEC-002 fix) |
| Local config | Unauthorized read | No secrets stored; restrictive permissions |
| Cached thumbnails | Privacy leak from filenames | Content-hashed keys, size-capped, deletable, disableable |
| Local data in transit to Drive | Interception | Handled by the official CLI's TLS stack |

Out of scope: compromise of the user's own machine, malicious/modified Proton
CLI binaries supplied by the user, and bugs in Proton AG's infrastructure.

---

## 5. Hardening Recommendations for Users

- Verify the Proton Drive CLI binary's provenance before installing it.
- Run PDUA from a user account; never as root.
- Consider `chmod 600 ~/.config/pdua/config.json`.
- Report unexpected script-hash mismatches immediately — they may indicate
  tampering on your system.

---

## 6. Changelog

- **1.2.10** — SEC-001, SEC-002, SEC-003 fixes; configuration unification;
  script pinning introduced; thumbnail cache added (opt-out capable).
