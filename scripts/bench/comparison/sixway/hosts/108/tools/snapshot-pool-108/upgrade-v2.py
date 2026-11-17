from pathlib import Path
k=Path('/opt/bench108/src/kuasar-fork/kuasar-io/kuasar')
p=k/'vmm/sandbox/src/service/mod.rs';s=p.read_text().replace('snapshot_pool::handle(&handle, &req, true)', 'snapshot_pool::handle(&handle, &req, "capture")').replace('snapshot_pool::handle(&handle, &req, false)', 'snapshot_pool::handle(&handle, &req, "bind")').replace('"snapshot-capture" =>', '"snapshot-prepare" => snapshot_pool::handle(&handle, &req, "prepare").await,\n            "snapshot-capture" =>');p.write_text(s)
p=k/'vmm/sandbox/src/service/snapshot_pool.rs';s=p.read_text().replace('capture: bool,','mode: &str,').replace('    let directory = template_path(req)?;', '    let capture = mode == "capture";\n    let directory = if mode == "prepare" { PathBuf::new() } else { template_path(req)? };')
s=s.replace('    let info = request(&api, "GET", "vm.info", None).await?;\n    let current = &info["config"];\n    let started = std::time::Instant::now();', '''    let started = std::time::Instant::now();
    let mut phases = Vec::new();
    let mut last = started;
    let mut mark = |name: &str| {
        let now = std::time::Instant::now();
        phases.push(json!({"phase":name,"ms":(now-last).as_secs_f64()*1000.0}));
        last = now;
    };
    let generic = Path::new(&sandbox.base_dir).join("generic-slot.json");
    let prepared = !capture && mode != "prepare" && generic.exists();
    let current: Value = if prepared {
        serde_json::from_slice(&tokio::fs::read(&generic).await?)?
    } else {
        request(&api, "GET", "vm.info", None).await?["config"].clone()
    };
    if mode == "prepare" {
        tokio::fs::write(&generic, serde_json::to_vec(&current)?).await?;
        std::fs::File::open(&generic)?.sync_all()?;
        std::fs::File::open(generic.parent().unwrap())?.sync_all()?;
        sandbox.network.as_ref().unwrap().fork_block(true).await?;
        sandbox.fork_agent_control(&uuid::Uuid::new_v4().to_string(), false).await?;
        request(&api, "PUT", "vm.delete", None).await?;
        sandbox.client.lock().await.take();
        return Ok(json!({"ok":true,"elapsed_ms":started.elapsed().as_secs_f64()*1000.0}));
    }
    mark("slot_configuration");''')
s=s.replace('        sandbox.network.as_ref().unwrap().fork_block(true).await?;\n        sandbox\n            .fork_agent_control(&uuid::Uuid::new_v4().to_string(), false)\n            .await?;\n        request(&api, "PUT", "vm.delete", None).await?;', '''        mark("stage_restore_files");
        if !prepared {
            sandbox.network.as_ref().unwrap().fork_block(true).await?;
            sandbox.fork_agent_control(&uuid::Uuid::new_v4().to_string(), false).await?;
            request(&api, "PUT", "vm.delete", None).await?;
        }
        mark("retire_generic_vm");''')
s=s.replace('        sandbox.dump().await?; // Identity/lifecycle ownership is durable before resume.', '        mark("restore_kvm_devices");\n        sandbox.dump().await?; // Identity/lifecycle ownership is durable before resume.\n        mark("persist_identity");')
s=s.replace('        sandbox.replace_fork_agent().await?;', '        mark("resume");\n        sandbox.replace_fork_agent().await?;\n        mark("agent_connection");')
s=s.replace('        sandbox.network.as_ref().unwrap().fork_block(false).await?;', '        mark("guest_identity_reset");\n        sandbox.network.as_ref().unwrap().fork_block(false).await?;\n        mark("connect_network");')
s=s.replace('"elapsed_ms":started.elapsed().as_secs_f64()*1000.0}))\n}', '"elapsed_ms":started.elapsed().as_secs_f64()*1000.0,"phases":phases}))\n}')
p.write_text(s)
p=k/'integrations/e2b/image_pool.py';s=p.read_text()
s=s.replace("response = self._create_image({'templateID': template, 'timeout': 86400})", "response = self._create_image({'templateID': template, 'timeout': 86400}, _snapshot_builder=True)")
s=s.replace('    def _create_image(self, body, parent=None):', '    def _create_image(self, body, parent=None, _snapshot_builder=False):')
old='''        sid = self.template_pool.lease(body, private=True, binding=dict(
            template_id=template, image_disk=image['disk'],
            image_sha256=image['sha256'], image_manifest=image['manifest']))'''
new='''        binding = dict(template_id=template, image_disk=image['disk'],
                       image_sha256=image['sha256'], image_manifest=image['manifest'])
        if _snapshot_builder:
            response = self._create_live(body)
            sid = response['sandboxID']
            try:
                self.jobs[sid].result(timeout=50)
                self.prepare_slot(sid, keep_running=True)
                with self.lock:
                    self.get(sid).update(binding, pool_state='binding')
                    self.save()
            except Exception:
                self.destroy(sid)
                raise
        else:
            sid = self.template_pool.lease(body, private=True, binding=binding)'''
# Replace only the legacy materialization function's lease, not snapshot claim.
pos=s.index('    def _create_image');s=s[:pos]+s[pos:].replace(old,new,1)
s=s.replace('    def prepare_slot(self, sid):','    def prepare_slot(self, sid, keep_running=False):')
s=s.replace("                raise RuntimeError('Generic block device preparation failed')", "                raise RuntimeError('Generic block device preparation failed')\n            if os.environ.get('E2B_SNAPSHOT_POOL') == '1' and not keep_running:\n                self.admin('sandbox-snapshot-prepare', sandbox_id=sid)")
p.write_text(s)
