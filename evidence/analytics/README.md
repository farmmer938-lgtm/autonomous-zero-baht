# External analytics evidence

This directory stores externally sourced measurement evidence only.

## Status rules

- `VERIFIED` requires a real external source plus provider, retrieval timestamp, verification reference, and numeric allowed metrics.
- `NOT_VERIFIED` is the default when no external evidence has been captured.
- Repository commits, workflow runs, and local logs prove system activity only; they do not prove traffic, conversions, transactions, revenue, or cash received.

## Capture workflow

1. Obtain metrics from an authorized external analytics surface.
2. Record the source URL, provider, retrieval timestamp, and an auditable verification reference.
3. Put only observed numeric metrics into an evidence record.
4. Run the validator in `engine.analytics.validate_external_evidence`.
5. Preserve the original evidence and validation result.
6. Use only `VERIFIED` evidence for `LEARN`.

Do not enter estimated, synthetic, placeholder, or model-generated metrics.

The repository currently has no verified external economic evidence unless a record is added from a real external source.
