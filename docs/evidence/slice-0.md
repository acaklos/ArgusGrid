# Slice 0 (identity baseline): quality gate evidence

Date: 2026-10-12. Environment: Windows 11, Python 3.12.10, Node.js 26.7, PostgreSQL 16.13 (portable, port 54329).

## Result

| Check | Evidence | Result |
|-------|----------|--------|
| Backend unit, API and security tests on real PostgreSQL | `backend`: `pytest` | **87 passed** |
| Frontend component tests | `frontend`: `vitest run` | **10 passed** |
| Browser tests through the running application | `devtools\e2e.ps1` (Playwright, Chromium, real backend and database) | **10 passed** |
| Shared-component check (SOL-011) | `npm run check:shared` | passed, 25 files scanned |
| TypeScript type check | `npx tsc --noEmit` | no errors |
| Theme contrast (design-system/tokens.md) | `devtools\contrast_check.py` | 0 of 24 pairs below the minimum, dark and light |
| Responsive check | e2e at 375 px width | navigation at the bottom, no horizontal scroll |
| Audit chain and append-only log | `test_audit_chain_is_intact_and_append_only` | passed, UPDATE and DELETE refused by the database |
| Secrets in source | `test_no_default_credentials_in_source`, `.gitignore` for `backend/data` | passed |

A defect found by the browser tests and fixed before the gate: on a 375 px screen the header and bottom
navigation overflowed horizontally. The layout now wraps (`base.css`), and the test stays in the suite.

## Requirement coverage in this slice

| Requirement | Covered by |
|-------------|-----------|
| ARG-001 login, logout, change password | `test_auth_flow.py`, e2e 1 to 3 and 8 |
| ARG-002 generated initial administrator | `test_initial_admin_forced_change_blocks_everything_else`, `test_initial_password_is_random_and_policy_valid`, `test_second_bootstrap_does_not_change_the_admin` |
| ARG-003 password policy | `test_password_policy.py`, `test_settings_pages.py`, `test_only_the_credential_service_writes_password_hashes` (PWD-021) |
| ARG-004 lockout | `test_lockout.py` (modes, escalation, window, persistence, consistency rules LCK-001 to LCK-005 and LCK-007) |
| ARG-010 RBAC at API level | `test_capabilities_are_enforced_on_the_server`, `test_roles_and_capabilities_live_in_the_database` |
| ARG-022 shared UI kit | `PasswordField`, `Dialog`, `ConfirmDialog`, `Field`, `Notify`, `DataTable`, `Shell`, `ApiClient`, `usePasswordPolicy`; guard script |
| Development helper rules (DEV-001 to DEV-004, DEV-007) | `test_structure.py` |

## Not done in this slice (stated so nothing is assumed)

| Item | Where it belongs |
|------|------------------|
| User management screens and API (create, edit, delete, lock, unlock, reset), e-mail with credentials | Slice 1 |
| E-mail settings and templates, password-expiry notification job | Slice 1 |
| Audit viewer and export; administrators hidden from lists (IDN-030 to IDN-034 tests need the user list) | Slice 1 |
| Service accounts with random passwords and credential file (IDN-014) | Slice 3 (simulator) |
| Two-factor module (switched off by decision AG-D-13) | Not planned |
| Timing equality of failed-login branches (LCK-011): the responses are identical and the code path spends one verification in each branch, but timing was **not measured** | Slice 6 hardening |
| Visual regression comparison across screens (SOL-012) | Slice 1 (more screens exist) |
| Automated accessibility scan (only keyboard, ARIA and focus behaviour were tested) | Slice 6 |
| Larger common-password list (about 120 entries now, AG-D-23) | Slice 6 |
| Shared throttle store for several workers (AG-D-24) | Slice 6 |
| Packaging, setup script, secret scan, clean-install proof | Slice 6 |
| Unlock through the API (the unlock service and its tests exist, the endpoint arrives with user management) | Slice 1 |

## How to reproduce

See `README.md`, section Tests.
