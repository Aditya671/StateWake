# Security Incident and Recovery Boundaries v0.1

## Evidence or artifact mutation

1. Stop relying on the affected artifact/receipt.
2. Preserve the failing evidence and verification output for investigation.
3. Compare against the last independently verified checkpoint where available.
4. Recover from the authoritative producer/source.
5. Re-ingest/rebuild only after the authoritative source is verified.

## Trust-checkpoint discrepancy

A rollback, broken sequence, conflicting checkpoint ID, or local-tip mismatch is a **security discrepancy**, not a repair instruction. Do not silently overwrite either side. Preserve both observations, identify the authoritative organizational source, and reconcile explicitly.

## Signing-key compromise

1. Revoke the affected key through the configured lifecycle provider.
2. Stop accepting new signatures from the compromised key according to trust policy.
3. Rotate to a replacement key.
4. Establish the replacement public-key digest in the trust configuration.
5. Re-attest/re-anchor affected evidence where required.
6. Record the incident and affected key/version range.

## Storage compromise

Local hash chains detect mutation of records that remain present. They cannot prove that an attacker did not delete an entire trailing segment. Use an independent trust checkpoint to detect this class of deletion.

## Network compromise

The built-in WSGI adapter requires HTTPS by default, but it does not terminate TLS or authenticate callers. If transport or caller authentication is compromised, isolate the adapter behind the deployment's trusted TLS/authentication boundary and investigate requests received during the exposure window.

## Recovery principle

Recovery restores verified state from authoritative inputs. It does not manufacture a new trusted history merely because the current local history is inconsistent.
