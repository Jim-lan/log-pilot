import os
import sys
from langchain_community.chat_models import ChatOllama
from langchain_community.embeddings import OllamaEmbeddings

# Set Env Var for Local Testing
os.environ["LLM_BASE_URL"] = "http://localhost:11434/v1"

def test_ollama():
    print("🤖 Testing Ollama Connection...")
    try:
        llm = ChatOllama(model="gemma4:e4b", base_url="http://localhost:11434")
        resp = llm.invoke("Hello, are you there?")
        print(f"✅ LLM Response: {resp.content}")
    except Exception as e:
        print(f"❌ LLM Connection Failed: {e}")

    print("\n🧠 Testing Embeddings...")
    try:
        embeddings = OllamaEmbeddings(model="gemma4:e4b", base_url="http://localhost:11434")
        vec = embeddings.embed_query("Hello world")
        print(f"✅ Embedding generated (dim: {len(vec)})")
    except Exception as e:
        print(f"❌ Embeddings Failed: {e}")

def test_ragas_import():
    print("\n📚 Testing Ragas Import...")
    try:
        from ragas import evaluate
        from ragas.metrics import faithfulness, answer_relevancy
        print("✅ Ragas imported successfully.")
    except ImportError as e:
        print(f"❌ Ragas Import Failed: {e}")
    except Exception as e:
        print(f"❌ Ragas Error: {e}")

if __name__ == "__main__":
    test_ollama()
    test_ragas_import()
