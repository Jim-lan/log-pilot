"""Idempotent pattern indexing using the same metadata format as LlamaIndex."""
import hashlib
import json


def upsert_pattern(collection, embedding_model, event):
    from llama_index.core.schema import TextNode, MetadataMode
    from llama_index.core.vector_stores.utils import node_to_metadata_dict
    identity = json.dumps([event.service_name, str(event.context['cluster_id'])])
    node_id = 'pattern-' + hashlib.sha256(identity.encode()).hexdigest()
    node = TextNode(id_=node_id, text=event.body, metadata={
        'service_name': event.service_name, 'severity': event.severity,
        'cluster_id': str(event.context['cluster_id']), 'type': 'log_pattern',
        'timestamp': str(event.timestamp)}, excluded_embed_metadata_keys=['timestamp'])
    embedding = embedding_model.get_text_embedding(node.get_content(metadata_mode=MetadataMode.EMBED))
    collection.upsert(ids=[node_id], embeddings=[embedding], documents=[event.body],
                      metadatas=[node_to_metadata_dict(node, remove_text=True, flat_metadata=True)])
    return node_id
