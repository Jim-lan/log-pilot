import re
from typing import Optional

class EvalScorer:
    """
    Calculates accuracy metrics for different agent tasks.
    """

    @staticmethod
    def score_regex(predicted_regex: str, expected_regex: str, sample_logs: list) -> float:
        """
        Scores a regex based on whether it matches the sample logs.
        Returns 1.0 if it matches all samples, 0.0 otherwise.
        We don't compare regex strings directly because different regexes can match the same text.
        """
        if not predicted_regex:
            return 0.0
            
        try:
            pattern = re.compile(predicted_regex)
            matches = [bool(pattern.match(log)) for log in sample_logs]
            return 1.0 if all(matches) else 0.0
        except re.error:
            return 0.0

    @staticmethod
    def score_sql(predicted_sql: str, expected_sql: str) -> float:
        """
        Scores SQL based on exact match or normalized match.
        Ideally, we would execute both against a DB, but for now we do string comparison.
        """
        if not predicted_sql:
            return 0.0
            
        # Simple normalization
        def normalize(s):
            return " ".join(s.lower().split())
            
        return 1.0 if normalize(predicted_sql) == normalize(expected_sql) else 0.0

    @staticmethod
    def score_rag(predicted_answer: str, expected_answer: str) -> float:
        """
        Scores RAG answers. 
        For now, simple keyword overlap. In production, use LLM-as-a-Judge.
        """
        if not predicted_answer:
            return 0.0
            
        # Jaccard similarity of tokens
        pred_tokens = set(predicted_answer.lower().split())
        exp_tokens = set(expected_answer.lower().split())
        
        if not exp_tokens:
            return 0.0
            
        intersection = pred_tokens.intersection(exp_tokens)
        union = pred_tokens.union(exp_tokens)
        
        return len(intersection) / len(union)
