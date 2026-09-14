import os
import hashlib
from jinja2 import Environment, FileSystemLoader

class PromptFactory:
    """
    Manages Jinja2 prompt templates.
    """
    def __init__(self, template_dir: str = "prompts"):
        # Resolve absolute path relative to project root
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
        full_path = os.path.join(base_path, template_dir)
        
        self.env = Environment(loader=FileSystemLoader(full_path))

    def create_prompt(self, agent: str, task: str, **kwargs) -> str:
        """
        Renders a prompt template.
        Usage: create_prompt("pilot_orchestrator", "classifier", query="...")
        """
        template_name = f"{agent}/{task}.j2"
        try:
            template = self.env.get_template(template_name)
            from shared.execution import current_budget
            budget = current_budget()
            if budget is not None:
                source, _, _ = self.env.loader.get_source(self.env, template_name)
                budget.provenance['templates'][template_name] = hashlib.sha256(source.encode()).hexdigest()
            return template.render(**kwargs)
        except Exception as e:
            raise ValueError(f"Failed to render template {template_name}: {e}")
