import unittest
from shared.utils.pii_masker import PIIMasker


class PrivacyContracts(unittest.TestCase):
    def test_nested_collections_are_masked_without_mutation(self):
        value = {"items": [{"email": "learner@example.com", "nested": ["192.168.1.2"]}]}
        masked = PIIMasker().mask_context(value)
        self.assertNotIn("learner@example.com", str(masked))
        self.assertNotIn("192.168.1.2", str(masked))
        self.assertEqual(value["items"][0]["email"], "learner@example.com")

    def test_outbound_secrets_are_redacted(self):
        from shared.privacy import redact_outbound
        text = 'email=learner@example.com password=hunter2 "api_key": "supersecret" Authorization: Bearer abc.def.ghi https://user:pass@internal.test/'
        cleaned = redact_outbound(text)
        for secret in ['learner@example.com', 'hunter2', 'supersecret', 'abc.def.ghi', 'user:pass']:
            self.assertNotIn(secret, cleaned)

    def test_operational_evidence_is_preserved(self):
        from shared.privacy import redact_outbound
        text = 'ERROR 503 fixture-service at 2026-09-13 count=12'
        self.assertEqual(redact_outbound(text), text)

    def test_private_key_block_is_redacted(self):
        from shared.privacy import redact_outbound
        text = 'before -----BEGIN PRIVATE KEY-----\nsecretbytes\n-----END PRIVATE KEY----- after'
        result = redact_outbound(text)
        self.assertNotIn('secretbytes', result)
        self.assertIn('before', result)
        self.assertIn('after', result)
