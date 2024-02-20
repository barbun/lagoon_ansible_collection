import unittest
import sys

sys.modules['ansible.utils.display'] = unittest.mock.Mock()
sys.modules['typing_extensions'] = unittest.mock.Mock()

from .....plugins.action.deploy_target_config import determine_required_updates

class DetermineUpdatesTester(unittest.TestCase):

    def test_update_required(self):
        existing_configs = []
        desired_configs = [
            {
                'branches': '^(main)$',
                'deployTarget': 1,
                'pullrequests': 'false',
            }
        ]
        
        additions_filtered, deletion_required = determine_required_updates(existing_configs, desired_configs)
        
        assert len(additions_filtered) == 1, "Expected one addition required"
        assert additions_filtered[0]['branches'] == '^(main)$', "Expected branches to match ^(main)$"
        assert additions_filtered[0]['deployTarget'] == 1, "Expected deployTarget to be 1"
        assert len(deletion_required) == 0, "Expected no deletions required"

    def test_update_not_required(self):
        existing_configs = [
            {
                'branches': '^(main)$',
                'deployTarget': {'id': 1, 'name': 'cluster.io'},
                'id': 1,
                'pullrequests': 'false',
                'weight': 1
            }
        ]
        desired_configs = [
            {
                'branches': '^(main)$',
                'deployTarget': 1,
                'pullrequests': 'false',
                'weight': 1
            }
        ]

        additions_filtered, deletion_required = determine_required_updates(existing_configs, desired_configs)

        assert len(additions_filtered) == 0, "Expected no additions required"
        assert len(deletion_required) == 0, "Expected no deletions required"

    def test_update_required_weight(self):
        existing_configs = [
            {
                'branches': '^(main)$',
                'deployTarget': {'id': 1, 'name': 'cluster.io'},
                'id': 1,
                'pullrequests': 'false',
                'weight': 1
            }
        ]
        desired_configs = [
            {
                'branches': '^(main)$',
                'deployTarget': 1,
                'pullrequests': 'false',
                'weight': 2
            }
        ]

        additions_filtered, deletion_required = determine_required_updates(existing_configs, desired_configs)

        assert len(additions_filtered) == 1, "Expected one addition required due to weight change"
        assert additions_filtered[0]['weight'] == 2, "Expected weight to be updated to 2"
        assert len(deletion_required) == 0, "Expected no deletions required"

    def test_update_required_cluster(self):
        existing_configs = [
            {
                'branches': '^(main)$',
                'deployTarget': {'id': 1, 'name': 'cluster.io'},
                'id': 1,
                'pullrequests': 'false',
                'weight': 1
            }
        ]
        desired_configs = [
            {
                'branches': '^(main)$',
                'deployTarget': 2,
                'pullrequests': 'false',
                'weight': 1
            }
        ]

        additions_filtered, deletion_required = determine_required_updates(existing_configs, desired_configs)

        assert len(additions_filtered) == 1, "Expected one addition required due to deployTarget change"
        assert additions_filtered[0]['deployTarget'] == 2, "Expected deployTarget to be updated to 2"
        assert len(deletion_required) == 0, "Expected no deletions required"

    def test_orphan_existing(self):
        existing_configs = [
            {
                'branches': '^(main)$',
                'deployTarget': {'id': 1, 'name': 'cluster.io'},
                'id': 1,
                'pullrequests': 'false',
                'weight': 1
            },
            {
                'branches': '^(develop)$',
                'deployTarget': {'id': 2, 'name': 'cluster.io'},
                'id': 2,
                'pullrequests': 'true',
                'weight': 1
            }
        ]
        desired_configs = [
            {
                'branches': '^(production|standby)$',
                'deployTarget': 1,
                'pullrequests': 'false',
                'weight': 1
            },
            {
                'branches': '^(develop|master)$',
                'deployTarget': 2,
                'pullrequests': 'true',
                'weight': 1
            }
        ] 

        additions_filtered, deletion_required = determine_required_updates(existing_configs, desired_configs)

        assert len(additions_filtered) == 2, "Expected two additions required due to changes"
        assert additions_filtered[0]['deployTarget'] == 1, "Expected the first addition to have deployTarget 1"
        assert additions_filtered[1]['deployTarget'] == 2, "Expected the second addition to have deployTarget 2"
        assert len(deletion_required) == 2, "Expecting 2 deletion of orphan deploytarget config"