set -eu
export PATH=/home/huawei/src/.tools/cargo/bin:$PATH
export CARGO_HOME=/home/huawei/src/.tools/cargo RUSTUP_HOME=/home/huawei/src/.tools/rustup CARGO_TARGET_DIR=/opt/bench108/build/snapshot-pool
cd /opt/bench108/src/kuasar-fork/kuasar-io/kuasar
cargo +stable test --offline --release -p vmm-task fork::tests -- --nocapture
