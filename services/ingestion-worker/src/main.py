import sys
import os
import time
import random
import json
from datetime import datetime
from typing import Dict, Any, List

# Add project root to python path to allow importing shared modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from shared.log_schema import LogEvent
from shared.db.duckdb_client import DuckDBConnector
from shared.utils.pii_masker import PIIMasker
from services.knowledge_base.src.store import KnowledgeStore
from shared.llm.client import LLMClient
from llama_index.core import Document
from shared.utils.template_miner import LogTemplateMiner
from shared.utils.log_parser import LogParser
from janitor import Janitor

# --- File Watcher Imports ---
import glob
import shutil
from queue import Queue
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class LogFileHandler(FileSystemEventHandler):
    def __init__(self, queue, allowed_extensions=(".log", ".md")):
        self.queue = queue
        self.allowed_extensions = allowed_extensions

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith(self.allowed_extensions):
            print(f"👀 Detected new file: {event.src_path}")
            self.queue.put(event.src_path)

    def on_moved(self, event):
        if not event.is_directory and event.dest_path.endswith(self.allowed_extensions):
            print(f"👀 Detected moved file: {event.dest_path}")
            self.queue.put(event.dest_path)

class FileWatcherConsumer:
    """Consumes logs from files in a directory using Watchdog."""
    def __init__(self, source_dir="data/source/landing_zone", processed_dir="data/source/processed"):
        self.source_dir = source_dir
        self.processed_dir = processed_dir
        self.file_queue = Queue()
        
        # Ensure directories exist
        os.makedirs(source_dir, exist_ok=True)
        os.makedirs(processed_dir, exist_ok=True)
        
        # 1. Scan existing files
        print(f"📂 Scanning {source_dir} for existing files...")
        existing_files = []
        for ext in ["*.log", "*.md"]:
            existing_files.extend(glob.glob(os.path.join(source_dir, ext)))
            
        for f in sorted(existing_files):
            print(f"   -> Found existing: {f}")
            self.file_queue.put(f)
            
        # 2. Start Watchdog
        self.observer = Observer()
        handler = LogFileHandler(self.file_queue)
        self.observer.schedule(handler, source_dir, recursive=False)
        self.observer.start()
        print(f"👀 Watching for new logs/docs in {source_dir}...")

    def __iter__(self):
        while True:
            if self.file_queue.empty():
                time.sleep(1) # Wait for files
                continue
                
            filepath = self.file_queue.get()
            filename = os.path.basename(filepath)
            processed_path = os.path.join(self.processed_dir, filename)
            
            # Handle duplicates/collisions in processed folder
            if os.path.exists(processed_path):
                base, ext = os.path.splitext(filename)
                ts = int(time.time())
                processed_path = os.path.join(self.processed_dir, f"{base}_{ts}{ext}")

            print(f"📖 Processing file: {filepath}")
            
            # Verify file stability (wait for write to finish)
            if not self._wait_for_file_stability(filepath):
                print(f"⚠️ Skipping unstable file: {filepath}")
                continue
                
            yield filepath, processed_path

    def _wait_for_file_stability(self, filepath: str, timeout: int = 5) -> bool:
        """Waits for file size to stop changing."""
        start_time = time.time()
        last_size = -1
        
        while time.time() - start_time < timeout:
            if not os.path.exists(filepath):
                return False
                
            current_size = os.path.getsize(filepath)
            if current_size == last_size and current_size > 0:
                return True
                
            last_size = current_size
            time.sleep(0.5) 
            
        return False

class LogIngestor:
    def __init__(self):
        print("DEBUG: Initializing LogIngestor...")
        
        print("DATA SOURCE: 📁 File Processor (Real-Time Watcher)")
        self.consumer = FileWatcherConsumer()
            
        self.miner = LogTemplateMiner(persistence_file="data/state/drain3_state.bin")
        print("DEBUG: Initializing KnowledgeStore...")
        self.kb = KnowledgeStore() # ChromaDB (might download models)
        print("DEBUG: KnowledgeStore initialized.")
        self.db = DuckDBConnector() # Acquire DB lock ONLY after heavy init
        self.pii_masker = PIIMasker()
        self.parser = LogParser()
        self.janitor = Janitor(self.kb) # Initialize Janitor
        self.llm_client = LLMClient() 
        self.batch_size = 5
        self.batch_buffer = []
        self.log_event_buffer = [] # Buffer for LogEvent objects
        
        # ==============================================================================
        # ⚙️  Ingestion Pipeline Overview
        # ==============================================================================
        # 1. Parse: Normalize raw text into structured key-value pairs.
        # 2. Mask: Redact sensitive info (IPs, Emails, etc.)
        # 3. Mine: Extract structural templates (Drain3) to group similar logs.
        # 4. Buffer & Flush: Persist to DuckDB (All Logs) and ChromaDB (Unique Patterns).
        # ==============================================================================

    # ... (Keep parse_log and flush_batch methods as is) ...
    # Wait, I cannot use '...' in replacement. I must provide the full content or clever chunks. 
    # Since I'm replacing the whole file logic or large parts, I should be careful.
    # The tool allows replacing a chunk. Let's target the LogFileHandler and FileWatcherConsumer and run loop first.

    def parse_log(self, raw_log: str) -> LogEvent:
        """Parses, masks, and enriches a raw log line."""
        # 1. Parser: Extract timestamp, severity, service, body
        parsed = self.parser.parse(raw_log)
        
        # 2. PII Masker: Replace sensitive patterns with <REDACTED>
        masked = self.pii_masker.mask_context(parsed)
        
        # 3. Template Miner (Drain3):
        #    - Discovers the underlying log structure (e.g. "User * failed to login").
        #    - Assigns a stable 'cluster_id' for grouping.
        mining_result = self.miner.mine_template(masked["body"])
        template_str = mining_result["template_mined"]
        cluster_id = mining_result["cluster_id"]
        change_type = mining_result["change_type"]
        
        # 4. Create LogEvent
        return LogEvent(
            timestamp=masked["timestamp"],
            severity=masked["severity"],
            service_name=masked["service_name"],
            body=masked["body"],
            # Map top-level optional fields
            department=masked.get("department"),
            environment=masked.get("environment"),
            host=masked.get("host"),
            region=masked.get("region"),
            context={
                "template_id": str(cluster_id), # Store ID as string
                "template_str": template_str,
                "change_type": change_type,
                **masked.get("context", {})
            }
        )

    def flush_batch(self):
        """Persists buffered logs to DuckDB and ChromaDB with DLQ support."""
        if not self.batch_buffer:
            return

        print(f"💾 Persisting batch of {len(self.batch_buffer)} logs...")
        
        # 1. DuckDB (Structured Data) - ALL LOGS
        try:
            self.db.insert_batch(self.batch_buffer)
        except Exception as e:
            print(f"❌ DuckDB Insert Failed: {e}")
            self._write_to_dlq(self.batch_buffer, "duckdb_insert_error")

        # 2. ChromaDB (Vector Data) - ONLY PATTERNS
        if self.log_event_buffer:
            try:
                print(f"🧠 Indexing {len(self.log_event_buffer)} new/updated patterns to ChromaDB...")
                self.kb.add_logs(self.log_event_buffer)
            except Exception as e:
                print(f"❌ ChromaDB Insert Failed: {e}")
                # We don't necessarily DLQ vector patterns as they are re-creatable, 
                # but let's log them to be safe.
                self._write_to_dlq([e.model_dump() for e in self.log_event_buffer], "chroma_insert_error")

        # Clear buffers
        self.batch_buffer = []
        self.log_event_buffer = []

    def _write_to_dlq(self, data: List[Dict[str, Any]], error_type: str):
        """Writes failed data to a Dead Letter Queue (JSON files)."""
        dlq_dir = "data/dlq"
        os.makedirs(dlq_dir, exist_ok=True)
        timestamp = int(time.time())
        filename = f"{error_type}_{timestamp}_{random.randint(1000,9999)}.json"
        filepath = os.path.join(dlq_dir, filename)
        
        try:
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2, default=str)
            print(f"⚠️  Written {len(data)} records to DLQ: {filepath}")
        except Exception as e:
            print(f"💀 CRITICAL: Failed to write to DLQ: {e}")

    def process_markdown_smart(self, filepath: str):
        """
        Intelligently ingests a markdown file by discovering topics and synthesizing knowledge cards.
        """
        print(f"🧠 Smart Ingestion: Reading {filepath}...")
        try:
            with open(filepath, 'r') as f:
                content = f.read()

            filename = os.path.basename(filepath)
            
            # Pass 1: Discovery
            prompt_discovery = f"""
            Read the following technical documentation.
            Identify all unique ERROR CODES or KEY TOPICS defined or explained in the text.
            
            IMPORTANT:
            - Look for headers (e.g., "# Error 503").
            - Look for TABLES containing error codes (e.g., "| 502 | Bad Gateway |").
            
            Return a JSON list of strings only.
            Example: ["Error 503", "502 Bad Gateway", "Authentication Failure"]
            
            Document:
            {content[:4000]} 
            (Truncated for discovery if too long)
            """
            
            print("   -> 🕵️  Discovering topics...")
            topics_json = self.llm_client.generate(prompt_discovery, model_type="smart")
            
            # Clean JSON using regex to find the first list
            import re
            json_match = re.search(r'\[.*\]', topics_json, re.DOTALL)
            if json_match:
                topics_json = json_match.group(0)
            
            try:
                topics = json.loads(topics_json)
                print(f"   -> Found {len(topics)} topics: {topics}")
            except:
                print(f"   ❌ Failed to parse topics JSON: {topics_json}")
                topics = ["General Content"] # Fallback

            # Pass 2: Synthesis
            documents = []
            for topic in topics:
                print(f"   -> 🧪 Synthesizing knowledge for: {topic}")
                prompt_synthesis = f"""
                You are a Technical Writer.
                Read the document below and extract EVERYTHING related to the topic: "{topic}".
                Combine scattered information (definitions, causes, fixes) into a single, comprehensive KNOWLEDGE CARD.
                
                Format:
                # {topic}
                **Definition**: ...
                **Review**: ...
                **Fix**: ...
                
                Keep it concise and actionable.
                
                Document:
                {content}
                """
                
                card_content = self.llm_client.generate(prompt_synthesis, model_type="smart") # Use smart model for quality
                
                # Create Document
                doc = Document(
                    text=card_content,
                    metadata={
                        "source": filename,
                        "topic": topic,
                        "type": "runbook_card"
                    }
                )
                documents.append(doc)
            
            # Index
            if documents:
                print(f"   -> 💾 Indexing {len(documents)} synthesized cards...")
                self.kb.add_documents(documents)
                
        except Exception as e:
            print(f"❌ Smart Ingestion Failed: {e}")


    def run(self):
        print("🚀 Starting Ingestion Worker (Real-Time Mode)...")
        print("🔒 PII Masking Enabled")
        print("🗄️  DuckDB Persistence Enabled")
        print("🧠 ChromaDB Persistence Enabled")
        
        self.janitor.run_cleanup(retention_days=30)
 
        try:
            # File Watcher Path (Logs + Markdown)
            for filepath, processed_path in self.consumer:
                filename = os.path.basename(filepath)
                
                if filename.endswith(".md"):
                    # Smart Ingestion for Runbooks
                    self.process_markdown_smart(filepath)
                else:
                    # Log Processing
                    try:
                        # wait slightly to ensure writing is done
                        time.sleep(0.5) 
                        with open(filepath, 'r') as f:
                            for line in f:
                                if line.strip():
                                    self.process_raw_log(line.strip())
                        self.flush_batch()
                    except Exception as e:
                        print(f"❌ Error reading log file {filepath}: {e}")
                        
                # Move to processed
                print(f"✅ Finished {filename}, moving to processed.")
                try:
                    shutil.move(filepath, processed_path)
                except Exception as e:
                        print(f"⚠️ Failed to move file {filepath}: {e}")

            # Safe cleanup
            self.db.close()

        except KeyboardInterrupt:
            print("\n🛑 Stopping worker...")
            self.flush_batch()
            self.db.close()
            
    def process_raw_log(self, raw_log):
        try:
            event = self.parse_log(raw_log)
            # 1. Add to DuckDB Buffer (Always)
            self.batch_buffer.append(event.model_dump())
            
            # 2. Add to ChromaDB Buffer (Only if Pattern Changed/Created)
            change_type = event.context.get("change_type")
            if change_type in ["cluster_created", "cluster_template_changed"]:
                print(f"✨ New Pattern Discovered: {event.context['template_str']}")
                pattern_event = LogEvent(
                    timestamp=event.timestamp,
                    severity=event.severity,
                    service_name=event.service_name,
                    body=event.context["template_str"], 
                    context={
                        "cluster_id": event.context["template_id"],
                        "is_pattern": True
                    }
                )
                self.log_event_buffer.append(pattern_event)
            
            print(f"✅ Processed: {event.timestamp} [{event.service_name}] {event.body}")
            
            if len(self.batch_buffer) >= self.batch_size:
                self.flush_batch()
        except Exception as e:
            print(f"⚠️ Failed to process log: {raw_log} -> {e}")

if __name__ == "__main__":
    ingestor = LogIngestor()
    ingestor.run()

