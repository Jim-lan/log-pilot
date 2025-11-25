import os
from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig
from drain3.file_persistence import FilePersistence

class LogTemplateMiner:
    """
    Wrapper around Drain3 for log template mining.
    Extracts constant templates from variable log messages.
    """
    def __init__(self, persistence_file: str = "data/state/drain3_state.bin", sim_th: float = 0.5):
        self.config = TemplateMinerConfig()
        self.config.load(os.path.join(os.path.dirname(__file__), "drain3.ini")) if os.path.exists("drain3.ini") else None
        self.config.profiling_enabled = False
        self.config.drain_sim_th = sim_th  # Similarity threshold (0.4-0.6 usually)

        # Ensure data directory exists
        os.makedirs(os.path.dirname(persistence_file), exist_ok=True)
        
        self.persistence = FilePersistence(persistence_file)
        self.miner = TemplateMiner(self.persistence, self.config)

    def mine_template(self, log_message: str) -> str:
        """
        Processes a log message and returns its template.
        This updates the internal Drain tree structure.
        """
        result = self.miner.add_log_message(log_message)
        return result["template_mined"]

    def get_total_clusters(self) -> int:
        return len(self.miner.drain.clusters)

    def save_state(self):
        """Saves the current state to disk."""
        import pickle
        # Convert clusters to list if it's a view, then pickle
        state = pickle.dumps(list(self.miner.drain.clusters))
        self.persistence.save_state(state)
