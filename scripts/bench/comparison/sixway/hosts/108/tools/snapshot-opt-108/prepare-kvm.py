from pathlib import Path
CH=Path('/opt/bench108/src/kuasar-fork/cloud-hypervisor/cloud-hypervisor');K=Path('/opt/bench108/src/kuasar-fork/kuasar-io/kuasar')
for name in ['vmm/src/lib.rs','vmm/src/api/mod.rs','vmm/src/api/http/mod.rs']:
 p=CH/name;back=Path('/opt/bench108/results/snapshot-opt-108/before')/name;back.parent.mkdir(parents=True,exist_ok=True);back.write_text(p.read_text())
p=CH/'vmm/src/lib.rs';s=p.read_text();s=s.replace('pub struct Vmm {','''struct PreparedRestoreVm {
    profile: hypervisor::HypervisorVmConfig,
    cpus: serde_json::Value,
    vm: Arc<dyn hypervisor::Vm>,
}

pub struct Vmm {''',1)
s=s.replace('    vm: VmOwnership,\n','    vm: VmOwnership,\n    prepared_restore_vm: Option<PreparedRestoreVm>,\n',1).replace('            vm: VmOwnership::None,\n','            vm: VmOwnership::None,\n            prepared_restore_vm: None,\n',1)
pos=s.index('    fn vm_restore(\n');end=s.index('    /// Handles the outcome',pos);part=s[pos:end]
part=part.replace('                self.vm_config = Some(Arc::clone(&vm_config));', '''                let reused_vm = if let Some(prepared) = &self.prepared_restore_vm {
                    let config = vm_config.lock().unwrap();
                    let mut profile: hypervisor::HypervisorVmConfig = (&*config).into();
                    profile.halt_poll_ns = Some(0);
                    if prepared.profile != profile
                        || prepared.cpus != serde_json::to_value(&config.cpus).unwrap()
                        || memory_restore_mode != MemoryRestoreMode::CopyOnWrite
                    {
                        return Err(VmError::ForkUnsupported("Prepared KVM profile does not match restore".into()));
                    }
                    drop(config);
                    Some(self.prepared_restore_vm.take().unwrap().vm)
                } else { None };
                self.vm_config = Some(Arc::clone(&vm_config));''',1)
part=part.replace('let mut vm = Vm::new(', 'let mut vm = Vm::new_with_inherited_memory(',1).replace('                    Some(memory_restore_mode),\n', '                    Some(memory_restore_mode),\n                    None,\n                    reused_vm,\n',1)
s=s[:pos]+part+s[end:]
pos=s.index('    fn vm_create(',s.index('impl RequestHandler for Vmm'))
s=s[:pos]+'''    fn vmm_prepare(&mut self, mut config: Box<VmConfig>) -> result::Result<(), VmError> {
        #[cfg(all(target_arch = "x86_64", feature = "kvm", not(any(feature = "tdx", feature = "sev_snp"))))]
        {
            if !matches!(self.vm, VmOwnership::None) || self.vm_config.is_some()
                || self.prepared_restore_vm.is_some() {
                return Err(VmError::VmAlreadyCreated);
            }
            config.validate().map_err(VmError::ConfigValidation)?;
            let mut profile: hypervisor::HypervisorVmConfig = config.as_ref().into();
            profile.halt_poll_ns = Some(0);
            let msrs = arch::x86_64::generate_required_msr_updates(self.hypervisor.as_ref(),
                config.cpus.profile, config.cpus.kvm_hyperv, config.cpus.nested)
                .map_err(|e| VmError::ForkUnsupported(format!("Preparing MSR profile: {e}")))?;
            let vm = Vm::create_hypervisor_vm(self.hypervisor.as_ref(), profile)?;
            let mut cpus = Vec::new();
            for id in 0..u32::from(config.cpus.boot_vcpus) {
                let cpu = vm.create_vcpu(id, None, msrs.clone())
                    .map_err(|e| VmError::ForkUnsupported(format!("Preparing vCPU: {e}")))?;
                cpus.push((id, cpu));
            }
            vm.park_fork_vcpus(cpus)
                .map_err(|e| VmError::ForkUnsupported(format!("Parking prepared vCPUs: {e}")))?;
            self.prepared_restore_vm = Some(PreparedRestoreVm {
                profile, cpus: serde_json::to_value(&config.cpus).unwrap(), vm,
            });
            return Ok(());
        }
        #[cfg(not(all(target_arch = "x86_64", feature = "kvm", not(any(feature = "tdx", feature = "sev_snp")))))]
        {
            let _ = config;
            Err(VmError::ForkUnsupported("KVM preparation requires ordinary x86_64 KVM".into()))
        }
    }

'''+s[pos:]
pos=s.index('    fn vm_create(',s.index('impl RequestHandler for Vmm'));end=s.index('    fn vm_boot',pos);part=s[pos:end].replace('if self.vm_config.is_some() {','if self.vm_config.is_some() || self.prepared_restore_vm.is_some() {',1);s=s[:pos]+part+s[end:]
s=s.replace('    fn vm_delete(&mut self) -> result::Result<(), VmError> {\n', '    fn vm_delete(&mut self) -> result::Result<(), VmError> {\n        self.prepared_restore_vm.take();\n',1);p.write_text(s)
p=CH/'vmm/src/api/mod.rs';s=p.read_text().replace('    VmRestore(#[source] VmError),','    VmRestore(#[source] VmError),\n\n    #[error("The VMM could not prepare KVM resources")]\n    VmmPrepare(#[source] VmError),',1)
s=s.replace('    fn vm_create(&mut self, config:', '''    fn vmm_prepare(&mut self, _config: Box<VmConfig>) -> Result<(), VmError> {
        Err(VmError::ForkUnsupported("KVM preparation is unavailable".into()))
    }

    fn vm_create(&mut self, config:''',1)
start=s.index('pub struct VmRestore;');end=s.index('pub struct VmResume;',start);action=s[start:end].replace('VmRestore','VmmPrepare').replace('type RequestBody = RestoreConfig;', 'type RequestBody = Box<VmConfig>;').replace('.vm_restore(config)', '.vmm_prepare(config)').replace('ApiError::VmmPrepare','ApiError::VmmPrepare');s=s[:start]+action+s[start:];p.write_text(s)
p=CH/'vmm/src/api/http/mod.rs';s=p.read_text().replace('    VmShutdown, VmSnapshot,','    VmShutdown, VmSnapshot, VmmPrepare,',1).replace('    r.routes.insert(\n        endpoint!("/vm.restore"),', '    r.routes.insert(endpoint!("/vmm.prepare"), Box::new(VmActionHandler::new(&VmmPrepare)));\n    r.routes.insert(\n        endpoint!("/vm.restore"),',1);p.write_text(s)
p=K/'vmm/sandbox/src/service/snapshot_pool.rs';s=p.read_text().replace('        request(&api, "PUT", "vm.delete", None).await?;\n        sandbox.client.lock().await.take();','''        request(&api, "PUT", "vm.delete", None).await?;
        request(&api, "PUT", "vmm.prepare", Some(current.clone())).await?;
        sandbox.client.lock().await.take();''',1)
s=s.replace('        sandbox.replace_fork_agent().await?;','''        // ForkControl below proves readiness and token ownership; an empty
        // Check round trip before it adds no safety. Delay event polling until
        // identity reset completes so it cannot contend with that transaction.
        let client = crate::client::new_sandbox_client(&sandbox.vm.socket_address()).await?;
        *sandbox.client.lock().await = Some(client);''',1)
s=s.replace('        mark("guest_identity_reset");','''        mark("guest_identity_reset");
        sandbox.forward_events().await;''',1) # check visibility below
p.write_text(s)
