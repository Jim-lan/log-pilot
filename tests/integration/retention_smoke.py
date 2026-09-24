"""Real vector activity metadata and production retention methods, with mock embedding."""
from datetime import datetime, timezone
import hashlib
import sys
import tempfile
from types import ModuleType

import chromadb
from chromadb.config import Settings
from llama_index.core.embeddings import MockEmbedding
from shared.log_schema import LogEvent
from shared.pattern_retention import pattern_activity, epoch
from shared.vector_upsert import upsert_pattern

# Import actual store methods without loading/downloading HuggingFace weights.
fake = ModuleType('llama_index.embeddings.huggingface')
fake.HuggingFaceEmbedding = lambda **kwargs: MockEmbedding(embed_dim=3)
sys.modules[fake.__name__] = fake
from services.knowledge_base.src.store import KnowledgeStore

with tempfile.TemporaryDirectory() as directory:
    collection = chromadb.PersistentClient(path=directory, settings=Settings(anonymized_telemetry=False)).get_or_create_collection('retention-fixture')
    embedding = MockEmbedding(embed_dim=3)
    event = LogEvent(timestamp=datetime(2026, 9, 20, tzinfo=timezone.utc), severity='ERROR', service_name='fixture', body='active pattern', context={'cluster_id': '1'})
    node_id = upsert_pattern(collection, embedding, event)
    event.timestamp = datetime(2020, 1, 1)
    upsert_pattern(collection, embedding, event)
    metadata = collection.get(ids=[node_id])['metadatas'][0]
    assert metadata['last_seen_at_unix'] == epoch(datetime(2026, 9, 20, tzinfo=timezone.utc))
    assert metadata['first_seen_at_unix'] == epoch(datetime(2020, 1, 1))
    collection.add(ids=['old', 'legacy'], documents=['old fixture', 'unknown legacy age'], embeddings=[[0.1] * 3] * 2,
        metadatas=[{'type': 'log_pattern', **pattern_activity(None, 10, 20)}, {'type': 'log_pattern', 'timestamp': '1970-01-01'}])
    store = KnowledgeStore.__new__(KnowledgeStore)
    store.collection = collection
    report = store.retention_candidates(100)
    assert report['candidate_id_hashes'] == [hashlib.sha256(b'old').hexdigest()]
    assert report['mutations'] == 0
    try:
        store.delete_older_than(100)
    except RuntimeError:
        pass
    else:
        raise AssertionError('Destructive retention was enabled')
    assert collection.count() == 3
    print('PASS: real vector activity is monotonic; active/legacy records retained; production deletion entry point disabled')
