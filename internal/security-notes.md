# Internal security notes (never packaged, never distributed)

This folder is excluded from deploy and publish packages. It holds the details of the emergency recovery path
that distributed documents must not describe (rules/19 OWN-013, rules/21 DEP-010).

## Emergency Owner: implementation summary (slice 0)

| Item | Implementation |
|------|----------------|
| Credential | Identifier and secret printed once by `devtools/owner_tool.py` for the envelope. Nothing is stored in plaintext |
| Sealed file | `backend/config/owner.sealed` (ignored by Git): installation id, identifier digest, Argon2id verifier, checksum |
| Installation binding | The file's installation id must equal the id stored in the database (`app_settings.installation`). A file from another installation is refused. First database initialisation adopts the id of an existing sealed file |
| Fail closed | Missing, unreadable, edited (checksum) or foreign file disables the path. No fallback and no creation of an owner |
| Login | The normal login form. An unknown user name goes to the owner check, which spends exactly one password verification, like any failed login |
| Rate limit | 5 failed owner attempts within 15 minutes pause the owner path for 15 minutes. Independent of ordinary lockouts |
| Authorization | Owner session has every capability. No user record exists, so the owner is absent from every list by construction |
| Logging | Owner actions go to `owner_log` (append-only trigger). In the normal audit they appear as "System". The owner login itself has no normal audit entry |
| UI | The lockout page text never mentions the owner (OWN-002 prevails over the example sentence in rules/18 section 3) |
| Tool | `devtools/owner_tool.py`, development only, excluded from packages |

## Known limits

- The checksum in the sealed file detects careless edits only. Someone with write access to the file can replace
  the verifier, but cannot make a foreign installation id match without also changing the database.
- The owner rate limit counts failures per installation, not per address.

## Evidence

Tests in `backend/tests/test_owner.py` (nine tests) and the browser tests T-OWN-02 and T-OWN-03.
