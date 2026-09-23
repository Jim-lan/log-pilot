"""Source provenance contracts using synthetic originals only."""
import hashlib
import unittest
from shared.document_identity import document_manifest, document_span, card_identity


class DocumentIdentityContracts(unittest.TestCase):
    def test_retry_source_distinction_and_versions(self):
        raw = b'# Recovery\nRetry the operation.\n'
        first = document_manifest('local-files', 'auth.md', raw)
        self.assertEqual(first, document_manifest('local-files', 'auth.md', raw))
        for namespace, key in [('local-files', 'billing.md'), ('other-source', 'auth.md')]:
            other = document_manifest(namespace, key, raw)
            self.assertEqual(first['content_sha256'], other['content_sha256'])
            self.assertNotEqual(first['source_id'], other['source_id'])
            self.assertNotEqual(first['version_id'], other['version_id'])
        changed = document_manifest('local-files', 'auth.md', raw + b'Updated.\n')
        self.assertEqual(first['source_id'], changed['source_id'])
        self.assertNotEqual(first['version_id'], changed['version_id'])
        self.assertEqual(card_identity(first['version_id'], 0), card_identity(first['version_id'], 0))
        self.assertNotEqual(card_identity(first['version_id'], 0), card_identity(first['version_id'], 1))
        self.assertNotEqual(card_identity(first['version_id'], 0), card_identity(changed['version_id'], 0))

    def test_ambiguous_or_unsafe_keys_and_invalid_content_are_rejected(self):
        for key in ['/absolute.md', '../a.md', 'a/../b.md', 'a//b.md', './a.md', 'a\\b.md', 'a\n.md', 'C:/a.md', '']:
            with self.subTest(key=key), self.assertRaises(ValueError):
                document_manifest('local-files', key, b'fixture')
        for namespace in ['', '../source', 'x' * 65]:
            with self.assertRaises(ValueError):
                document_manifest(namespace, 'a.md', b'fixture')
        for raw in [b'', b'\xff', 'text']:
            with self.assertRaises(ValueError):
                document_manifest('local-files', 'a.md', raw)

    def test_source_spans_preserve_unicode_and_crlf_bytes(self):
        raw = '# Café\r\nRetry.\r\n'.encode('utf-8')
        manifest = document_manifest('local-files', 'runbooks/a.md', raw)
        self.assertEqual(manifest['byte_length'], 17)
        span = document_span(raw, 9, 15)
        self.assertEqual(raw[span['start_byte']:span['end_byte']], b'Retry.')
        self.assertEqual(span['content_sha256'], hashlib.sha256(b'Retry.').hexdigest())
        for start, end in [(6, 8), (0, 6), (-1, 3), (3, 3), (0, 99), (False, 3)]:
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                document_span(raw, start, end)
        for ordinal in [-1, 32, True, '0']:
            with self.assertRaises(ValueError):
                card_identity(manifest['version_id'], ordinal)
