# Slice 1 (administration): quality gate evidence

Date: 2026-10-12. Environment as in slice 0 (Windows 11, Python 3.12.10, Node.js 26.7, PostgreSQL 16.13).

## Result

| Check | Evidence | Result |
|-------|----------|--------|
| Backend tests on real PostgreSQL | `backend`: `pytest` | **139 passed** (87 from slice 0, 52 new) |
| Frontend component tests | `vitest run` | **10 passed** |
| Browser tests through the running application, real database and a real SMTP sink | `devtools\e2e.ps1` | **20 passed** (10 identity, 10 administration) |
| SMTP delivery to a real server | `test_real_smtp_delivery_to_a_local_server` (aiosmtpd) and the browser sink | passed |
| Shared-component check (SOL-011) | `npm run check:shared` | passed, 32 files |
| Type check, contrast check | `tsc --noEmit`, `contrast_check.py` | no errors, 0 of 24 pairs below minimum |
| Audit chain after all operations | `test_audit_verify_endpoint`, e2e "Verify integrity" | intact |

## Defects found by the tests and fixed in this slice

| Defect | Found by | Fix |
|--------|----------|-----|
| Editing role capabilities failed with a unique-key violation (new rows were inserted before old ones were deleted) | `test_roles_audit.py` | Only the difference is applied |
| A template that triggers the sandbox returned HTTP 500 | `test_template_sandbox_blocks_attribute_tricks` | Render errors become a validation problem; a saved template that fails to render falls back to the default so security mails are never lost |
| Mail body fixtures assumed 7-bit text; passwords containing `=` are quoted-printable encoded on the wire | browser test | Test decodes quoted-printable; no application change needed |
| The e-mail page showed a conflict list without a heading | browser test | Same heading as the other settings pages |
| Word wrapping broke columns mid-word in narrow tables | screenshot review | `overflow-wrap: break-word` |

The browser tests also confirmed that the per-address login throttle works in a real browser (a suite signing in
more than 20 times a minute from one address was refused). The test database raises the limit; production keeps 20.

## Requirement coverage

| Requirement | Covered by |
|-------------|-----------|
| ARG-005 user CRUD, lock, unlock, reset, separate capabilities | `test_users.py` (20 tests), e2e create, lock, unlock |
| ARG-006 credentials by e-mail on create, unlock with reset, password reset; never stored in readable form after sending | `test_credentials_mail_is_delivered_then_wiped_from_the_outbox`, `test_unlock_with_reset_sends_a_new_password_by_mail`, e2e "creating a user sends the credentials by e-mail" |
| ARG-007 SMTP settings page, secret never returned, stored encrypted | `test_smtp_password_is_never_returned_and_is_stored_encrypted`, e2e |
| ARG-008 templates: catalogue, variables, preview, versions, locale, expiry notice | `test_email.py` (22 tests), e2e custom template |
| ARG-009 audit view, filters, old and new values, export, integrity | `test_roles_audit.py`, e2e audit page |
| ARG-010 RBAC at API level | every endpoint checked without a session and without the capability |
| ARG-011 / IDN-030 to IDN-034 hidden administrators | `test_lower_roles_never_see_administrator_accounts`, `test_404_for_hidden_and_for_missing_look_the_same`, audit masking test, e2e |
| IDN-004 separate capabilities, roles editable at runtime | `test_edit_does_not_imply_lock_or_reset`, role tests |
| IDN-003 role reduction revokes sessions | `test_capabilities_edit_at_runtime_takes_effect_and_ends_sessions` |
| Rule 18 section 2 notification of the administrator and other administrators | `test_account_lock_notifies_the_user_and_other_administrators` |

## Not done in this slice

| Item | Where it belongs |
|------|------------------|
| Service accounts with generated passwords and credential file (IDN-014) | Slice 3 (simulator) |
| Timing of the failed-login branches was not measured (identical responses only) | Slice 6 |
| Visual regression across screens (SOL-012) and an automated accessibility scan | Slice 6 |
| Larger common-password list, shared throttle store (AG-D-23, AG-D-24) | Slice 6 |
| In-application display of the audit "System" label explanation for auditors | Possible UI note, not required |
| Packaging, setup script, clean-install proof | Slice 6 |
| Mail delivery over STARTTLS and SSL against a real server was not exercised (only plain SMTP to the sink); the code path uses `smtplib` with default certificate verification | Slice 6 pilot environment |

## Reproduce

See `README.md`, section Tests. The browser runner starts its own server and SMTP sink and stops only those two
processes.
