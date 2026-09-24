"""Idempotent pattern indexing using the same metadata format as LlamaIndex."""
import hashlib
import json
import time

from shared.pattern_retention import pattern_activity


def upsert_pattern(collection, embedding_model, event):
    from llama_index.core.schema import TextNode, MetadataMode
    from llama_index.core.vector_stores.utils import node_to_metadata_dict
    identity = json.dumps([event.service_name, str(event.context['cluster_id'])])
    node_id = 'pattern-' + hashlib.sha256(identity.encode()).hexdigest()
    stored = collection.get(ids=[node_id], include=['metadatas'])
    previous = stored['metadatas'][0] if stored['ids'] else None
    activity = pattern_activity(previous if previous is not None else ({} if stored['ids'] else None),
                                event.timestamp, time.time())
    node = TextNode(id_=node_id, text=event.body, metadata={
        'service_name': event.service_name, 'severity': event.severity,
        'cluster_id': str(event.context['cluster_id']), 'type': 'log_pattern',
        'timestamp': str(event.timestamp), **activity},
        excluded_embed_metadata_keys=['timestamp', *activity],
        excluded_llm_metadata_keys=list(activity))
    embedding = embedding_model.get_text_embedding(node.get_content(metadata_mode=MetadataMode.EMBED))
    collection.upsert(ids=[node_id], embeddings=[embedding], documents=[event.body],
                      metadatas=[node_to_metadata_dict(node, remove_text=True, flat_metadata=True)])
    return node_id


def upsert_document_card(collection, embedding_model, payload):
    """Index one already-journaled card without introducing random chunk IDs."""
    from llama_index.core.schema import TextNode, MetadataMode
    from llama_index.core.vector_stores.utils import node_to_metadata_dict
    node = TextNode(id_=payload['node_id'], text=payload['text'], metadata=payload['metadata'])
    embedding = embedding_model.get_text_embedding(node.get_content(metadata_mode=MetadataMode.EMBED))
    collection.upsert(ids=[node.node_id], embeddings=[embedding], documents=[payload['text']],
                      metadatas=[node_to_metadata_dict(node, remove_text=True, flat_metadata=True)])
    return node.node_id
