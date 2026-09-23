"""Real Chroma/LlamaIndex adapter smoke, synthetic embeddings and disposable storage."""
import tempfile
import subprocess
import sys
import os
from datetime import datetime
import chromadb
from chromadb.config import Settings
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.vector_stores import VectorStoreQuery
from shared.log_schema import LogEvent
from shared.vector_upsert import upsert_pattern

class FixtureEmbedding:
    def get_text_embedding(self, text):
        return [0.1, 0.2, 0.3]

def exercise(directory, reopen=False):
    client = chromadb.PersistentClient(path=directory, settings=Settings(anonymized_telemetry=False))
    collection = client.get_or_create_collection('fixture-patterns')
    event = LogEvent(timestamp=datetime(2026, 9, 17), severity='ERROR', service_name='fixture',
                     body='first pattern', context={'cluster_id': '1'})
    if reopen:
        assert collection.count() == 1
        assert collection.get()['documents'] == ['updated pattern']
    first_id = upsert_pattern(collection, FixtureEmbedding(), event)
    upsert_pattern(collection, FixtureEmbedding(), event)
    assert collection.count() == 1
    event.body = 'updated pattern'
    assert upsert_pattern(collection, FixtureEmbedding(), event) == first_id
    assert collection.count() == 1
    result = ChromaVectorStore(chroma_collection=collection).query(
        VectorStoreQuery(query_embedding=[0.1, 0.2, 0.3], similarity_top_k=1))
    assert result.nodes[0].node_id == first_id
    assert result.nodes[0].get_content() == 'updated pattern'
    assert result.nodes[0].metadata['cluster_id'] == '1'
    print('PASS: real Chroma upsert retry/update and LlamaIndex retrieval preserve one stable node')

if __name__ == '__main__':
    if len(sys.argv) == 3:
        exercise(sys.argv[2], reopen=sys.argv[1] == 'reopen')
        # Simulate abrupt exit after acknowledged vector writes, without Python cleanup.
        sys.stdout.flush()
        os._exit(0)
    else:
        with tempfile.TemporaryDirectory() as directory:
            for phase in ('write', 'reopen', 'reopen'):
                subprocess.run([sys.executable, '-B', __file__, phase, directory],
                               check=True, timeout=90)
        print('PASS: acknowledged vector state survives abrupt process exit and two replays')
