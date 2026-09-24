"""Real Drain3 clustering and persisted state, confined to disposable storage."""
import os
from pathlib import Path
import tempfile
import unittest

from shared.utils.template_miner import LogTemplateMiner


class TemplateMinerContracts(unittest.TestCase):
    def test_explicit_snapshot_restores_template_identity_and_counts(self):
        with tempfile.TemporaryDirectory(dir=os.environ['LOGPILOT_TEST_SCRATCH']) as directory:
            state = str(Path(directory) / 'state.bin')
            miner = LogTemplateMiner(state)
            first = miner.mine_template('Connection failed for host alpha')
            second = miner.mine_template('Connection failed for host beta')
            self.assertEqual(first['cluster_id'], second['cluster_id'])
            self.assertEqual(second['template_mined'], 'Connection failed for host <*>')
            miner.mine_template('Connection failed for host gamma')
            miner.save_state()
            restored = LogTemplateMiner(state)
            result = restored.mine_template('Connection failed for host delta')
            self.assertEqual(result['cluster_id'], first['cluster_id'])
            self.assertEqual(result['cluster_size'], 4)
            self.assertEqual(result['template_mined'], second['template_mined'])
            different = restored.mine_template('Disk full')
            self.assertNotEqual(different['cluster_id'], first['cluster_id'])
            self.assertEqual(restored.get_total_clusters(), 2)
            restored.save_state()
            self.assertEqual(LogTemplateMiner(state).get_total_clusters(), 2)
