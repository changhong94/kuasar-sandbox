"""Isolated lifecycle control-flow tests; never stop real services or delete real data."""
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import bench_lifecycle as lifecycle


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.patches=patch.object(lifecycle,'timing_patches')
        self.manager=self.patches.start()
        self.addCleanup(self.patches.stop)
        self.manager.fingerprint.return_value={'orchestrator':'test','sandboxer':'test'}

    def test_aggregate_cleanup_preserves_download_cache_and_is_repeatable(self):
        with tempfile.TemporaryDirectory() as directory:
            repo=Path(directory)
            cache=repo/'build/tarball'
            cache.mkdir(parents=True)
            (cache/'zot').write_bytes(b'cached download')
            (cache/'checksums.sha256').write_text('checksum')
            (repo/'bin').mkdir()
            (repo/'bin/node-ctl').write_text('binary')
            (repo/'build/e2e-tools').mkdir()
            (repo/'build/e2e-tools/zot').write_text('executable')
            (repo/'build/log').write_text('generated')
            (repo/'README.md').write_text('source')
            lifecycle.clean_aggregate(repo)
            lifecycle.clean_aggregate(repo)
            self.assertEqual((cache/'zot').read_bytes(),b'cached download')
            self.assertEqual((cache/'checksums.sha256').read_text(),'checksum')
            self.assertEqual(list((repo/'build').iterdir()),[cache])
            self.assertFalse((repo/'bin').exists())
            self.assertEqual((repo/'README.md').read_text(),'source')

    def test_healthy_deployment_is_reused(self):
        with patch.object(lifecycle,'units',return_value=list(lifecycle.UNITS)), patch.object(lifecycle,'healthy',return_value=True), patch.object(lifecycle,'run') as run:
            with tempfile.TemporaryDirectory() as directory:
                state=Path(directory)
                (state/'timing-build.json').write_text('{"orchestrator":"test","sandboxer":"test"}')
                with patch.object(lifecycle,'STATE',state):
                    lifecycle.prepare(False,1)
            run.assert_not_called()

    def test_unhealthy_existing_deployment_is_not_overwritten(self):
        with patch.object(lifecycle,'units',return_value=list(lifecycle.UNITS)), patch.object(lifecycle,'healthy',return_value=False), patch.object(lifecycle,'run') as run:
            with self.assertRaises(RuntimeError): lifecycle.prepare(False,1)
            run.assert_not_called()

    def test_build_failure_prevents_deployment(self):
        with patch.object(lifecycle,'units',return_value=[]), patch.object(lifecycle,'run',side_effect=subprocess.CalledProcessError(1,'build')) as run:
            with self.assertRaises(subprocess.CalledProcessError): lifecycle.prepare(False,1)
            self.assertEqual(run.call_count,1)

    def test_fresh_prepare_builds_then_deploys(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(lifecycle,'STATE',Path(directory)), patch.object(lifecycle,'units',return_value=[]), patch.object(lifecycle,'healthy',return_value=True), patch.object(lifecycle,'run') as run:
                lifecycle.prepare(False,1)
                commands=[c.args[0] for c in run.call_args_list]
                self.assertEqual(commands[0][1].name,'build-official.sh')
                self.assertIn('verify-prebuilt',commands[1])
                self.assertEqual(commands[2][1].name,'deploy-source.sh')

    def test_live_deployment_blocks_build_cleanup(self):
        with patch.object(lifecycle,'units',return_value=list(lifecycle.UNITS)), patch.object(lifecycle,'active',return_value=True), patch.object(lifecycle,'run') as run:
            with self.assertRaises(RuntimeError): lifecycle.clear(False,True,False)
            run.assert_not_called()

    def test_failed_stop_preserves_owned_data(self):
        with tempfile.TemporaryDirectory() as directory:
            data=Path(directory)
            (data/'.kuasar-demo-owner').write_text('kuasar-demo-owner-v1\nuid=0\ngid=0\n')
            keep=data/'important';keep.write_text('keep')
            with patch.object(lifecycle,'DATA',data), patch.object(lifecycle,'units',return_value=['kuasar-hong-node.service']), patch.object(lifecycle,'run',side_effect=subprocess.CalledProcessError(1,'stop')):
                with self.assertRaises(subprocess.CalledProcessError): lifecycle.clear(True,False,False)
            self.assertTrue(keep.exists())

    def test_foreign_data_marker_blocks_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            data=Path(directory);(data/'.kuasar-demo-owner').write_text('foreign')
            with patch.object(lifecycle,'DATA',data), patch.object(lifecycle,'units',return_value=[]), patch.object(lifecycle,'run') as run:
                with self.assertRaises(RuntimeError): lifecycle.clear(True,False,False)
                run.assert_not_called()


if __name__=='__main__': unittest.main()