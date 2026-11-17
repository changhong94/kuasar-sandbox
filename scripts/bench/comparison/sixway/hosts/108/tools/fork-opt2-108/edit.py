from pathlib import Path
q=Path('/opt/bench108/src/kuasar-fork/kuasar-io/kuasar/integrations/e2b')
p=q/'template_pool.py';s=p.read_text();s=s.replace('            job.result(timeout=50)\n','            job.result(timeout=50)\n            prepare = getattr(self.backend, "prepare_slot", None)\n            if prepare:\n                prepare(sid)\n');p.write_text(s)
p=q/'vm_backend.py';s=p.read_text().replace("'oci_config', 'entrypoint_pid'):","'oci_config', 'entrypoint_pid', 'slot_disk'):");p.write_text(s)
p=q/'image_pool.py';s=p.read_text();s=s.replace('        super().__init__(args)\n','        self.slot_disks = None\n        if os.environ.get("E2B_PREPARE_IMAGE_DEVICE") == "1":\n            from slot_disk import SlotDisks\n            self.slot_disks = SlotDisks(Path(args.state).parent / "slot-disks", self.image_catalog)\n        super().__init__(args)\n',1)
s=s.replace("                add_image_disk(info['live_fork']['api_socket'], image['disk'])","                if record.get('slot_disk'):\n                    self.slot_disks.bind(record['slot_disk'], image)\n                else:\n                    add_image_disk(info['live_fork']['api_socket'], image['disk'])",1)
s=s.replace('    def execute_process(self, sid, process, user=None):','''    def prepare_slot(self, sid):
        if getattr(self, 'slot_disks', None) is None:
            return
        with self.operation(sid):
            path = str(self.slot_disks.path / (sid + '.raw'))
            with self.lock:
                self.get(sid)['slot_disk'] = path
                self.save()  # ownership precedes file creation and attachment
            self.slot_disks.create(path)
            info = self.admin('sandbox-get', sandbox_id=sid)['live_fork']
            add_image_disk(info['api_socket'], path)
            result = vm_rpc.execute(info['vsock_socket'],
                                    [os.environ['E2B_IMAGE_MOUNT_HELPER'], 'prepare'])
            if result['exit_code']:
                raise RuntimeError('Generic block device preparation failed')

    def destroy(self, sid):
        super().destroy(sid)
        if getattr(self, 'slot_disks', None) is not None:
            with self.lock:
                self.slot_disks.collect({r['slot_disk'] for r in self.records.values() if r.get('slot_disk')})

    def execute_process(self, sid, process, user=None):''')
s=s.replace("            from server import vm_process_argv\n            return self.execute(sid, vm_process_argv(process))",'''            helper = os.environ.get('E2B_IMAGE_MOUNT_HELPER')
            if helper:
                envs = process.get('envs', {})
                argv = [helper, 'exec', record['exec_root'], process.get('cwd') or '/',
                        str(len(envs)), *[k+'='+v for k, v in envs.items()],
                        process['cmd'], *process.get('args', [])]
                return self.raw_execute(sid, argv)
            from server import vm_process_argv
            return self.execute(sid, vm_process_argv(process))''')
s=s.replace("            return vm_rpc.execute(record['vsock_socket'], argv, stdin)","            started = time.perf_counter_ns()\n            result = vm_rpc.execute(record['vsock_socket'], argv, stdin)\n            trace_timing('execute_rpc', started, sid=sid, guest=result.get('timing'))\n            trace_timing('execute_total', started, sid=sid)\n            return result")
p.write_text(s)
