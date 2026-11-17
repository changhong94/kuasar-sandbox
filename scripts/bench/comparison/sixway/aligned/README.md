# Aligned six-product startup tests

This directory versions the 113 aligned suite and adds Python, Node.js and
Ruby startup sampling through the same SDK/CLI adapters. It is shared by 108
and 113; endpoints, namespaces, credentials **paths**, and template IDs belong
in a host-specific configuration. `config.json` records the historical 113
Python setup; it is not a portable deployment installer.

## Protocol

- Six products: Kuasar off, UFFD, fork, mlink, AgentENV and CubeSandbox.
- 2 vCPU / 2048 MiB. Configurable startup pools must have capacity 2.
- Each language: one disposable identity preflight per product, one separately
  recorded warmup, then 50 serial samples per product with rotating order.
- One create request starts the clock. The first exec stream emits a random
  shell marker, then **starts a fresh interpreter** to print another random
  marker. Timing ends when the client receives that full line, not API return
  or process exit. No failed sample retries or sample trimming.
- `native_ready_ms`, `interpreter_print_ms`, `native_to_interpreter_ms`, API,
  cleanup and refill times are separate. Python also retains legacy
  `python_print_ms` / `native_to_python_ms` fields for old reports. Node/Ruby
  never populate Python fields.
- Import, image conversion, capture, cache preparation and refill are outside
  request latency and must be reported separately. No interpreter is run in a
  template or recaptured after identity preflight/warmup. The runner checks
  readiness; it does not silently resize pools or prepare them inside timing.

## Prepare and configure

Copy a host's endpoint configuration outside the repository. Merge the
`_languages` object from `languages.example.json` and replace **all six**
template IDs for each requested language. Images are fixed to their supplied
amd64 manifest digests. Do not install Node/Ruby into the Python image: build
or import each product's template from the same official language image.
Normal product-specific guest-agent injection is still necessary. Use native
`sleep` or the product agent as the template entrypoint, never the interpreter.

For each language, prepare the six templates through the products' normal
import/build paths before running the matrix. Configure mlink's template
storage and full-memory prewarm and fork's image catalog/file templates while
keeping their shared VM pool at capacity 2; no separate per-image fork VM pool.
`prepare_templates.py`, `prepare_mlink.py`, `configure.py` and deployment helpers
preserve the original Python preparation recipe. They are host-specific
historical scripts, **not** Node/Ruby importers; do not run them blindly on 108.
New language template IDs are deployment state and intentionally not invented
in the example. Missing/unprepared entries fail before timed requests.

Provide per-product `resource_cgroup_patterns` (and optional exclusions) to
attribute preparation resources on the selected host. Missing ownership is
reported as unsupported, not zero. mlink can set `pool_status_url` to its own
admin endpoint; 113's historical default is port 29082.

```bash
export SIXWAY_ROOT=/path/to/host-specific-sixway-work
# Use the deployed SDK virtualenv; run with namespace/root access as required.
python startup_languages.py /path/to/config.json --out "$SIXWAY_ROOT/results/languages-new"
# A subset (still all six products, 50 measured + 1 warmup each):
python startup_languages.py /path/to/config.json --languages node ruby \
  --out "$SIXWAY_ROOT/results/node-ruby-new"
```

The wrapper first validates all template mappings. Disposable preflight checks
2 CPUs, approximately 2 GiB guest RAM, no existing Python/Node/Ruby process,
and identical interpreter version + SHA256 across six products. Full OCI
provenance and injected-library identity must also be retained by image
preparation; identical interpreter hashes alone do not prove identical images.
Each language has its own samples, config, warmup, stages and CSV. Existing
full CPU/IO/storage/memory tests remain Python workloads and are not silently
redefined as Node/Ruby tests. Startup pool expansion to 64 for resource tests
remains a separate preparation step.

## Validation

```bash
python -m unittest discover -s . -p 'test_*.py' -v
python summarize_startup.py --config /path/to/config.json --language ruby \
  --input /path/to/results/ruby --out /path/to/results/ruby
```

The new collector was smoke-tested with real Node/Ruby guests on 108 and its
stream/cleanup paths are unit-tested. The old 300 Python samples were re-read
with the generalized summarizer and retained their statistics. This code change
does not claim a new six-product Node/Ruby performance result: those require
preparing the corresponding six templates and running the matrix.

## Completed 113 three-language run

The host-specific preparation, mlink per-language policy switching, matrix
orchestration and independent-destruction checks for the completed 900-sample
run are in [hosts/113/tools/three-language-20261117](../hosts/113/tools/three-language-20261117/README.md).
That runner handles the shared mlink storage budget between languages; the
generic wrapper above does not switch deployment policies automatically.
The shared collector in this directory was unchanged. PDF/report generation
and output artifacts are intentionally excluded from that code archive.
