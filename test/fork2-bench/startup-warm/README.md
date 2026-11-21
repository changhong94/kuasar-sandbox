# Warm startup comparison

This host-113 harness measures fork2, the old fork comparator and mlink.
It expects the existing isolated deployment paths referenced in bench.py.
It does not deploy, patch, or stop the old fork implementation.

Each product/language gets one excluded warmup and 50 serial samples.
Ready ends at client receipt of the shell marker; print ends at receipt
of a fresh interpreter's random marker. Both start before create.

Prepare new and old fork templates with the same uniform 512 MiB regular
file read budget. No interpreter runs during preparation and no language
specific file lists are used. Prepared VM slots remain image independent.
Mlink uses its existing native full-warm/L2 policy.

Before each fork request, verify full host carrier page residency; read
only files that are not fully resident. This preserves the historical
local-warm cache state without rereading already resident files.
Record all preparation outside request-to-marker latency.

Use persistent disks, 2 vCPUs, 2 GiB RAM, 64 reserve slots and 8 preparation
workers. Do not compare with zero-budget guest-cache preparation without
explicitly labelling that policy difference.

Run bench.py in the configured host environment. It rotates product order,
records every sample and deletes only instances it creates. Existing
services and templates must be prepared before starting it. Preserve
results outside the repository. summarize.py expects results/startup and
results/template-preparation.json adjacent to it in the result directory.
