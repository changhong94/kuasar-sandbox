# source this — 本 bench 专属 conductor（:4443，config/config-4443.yaml，用 /root/sandbox 重建的 node-ctl），e2b SDK 经 E2B_API_URL 连入。
export E2B_DOMAIN='sandboxes.demo.local'
export E2B_API_URL='https://api.sandboxes.demo.local:4443'   # 独立 conductor（重建的 node-ctl，config-4443.yaml）
export E2B_SANDBOX_URL='https://sandboxes.demo.local:8443'   # 数据面走 proxy data_listen（:8443，0904 起 4443 仅控制面）
export E2B_API_KEY="" # Set in the private deployment environment file.
export E2B_ACCESS_TOKEN="" # Set in the private deployment environment file.
export SSL_CERT_FILE='/root/sandbox/e2b-bench-file-bare/config/tls.crt'
export REQUESTS_CA_BUNDLE='/root/sandbox/e2b-bench-file-bare/config/tls.crt'
export NO_PROXY='*'
export E2B_NODE_CTL_SOCKET='/tmp/e2b-bench-4443/node-ctl.socket'
export E2B_RUN_ROOT='/tmp/e2b-bench-4443/run'   # conductor run 目录（= config-4443.yaml paths.run_root）；留作参考，bench 脚本已改走 node proxy、不再读此变量
export E2B_BIN='/root/sandbox/orchestrator/bin'
export E2B_SAVED_DIR='/mnt/sfs_turbo/e2b-bench-file-optimization/snaps'
