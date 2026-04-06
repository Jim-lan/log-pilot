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

    @staticmethod
    def grade_structured_output(response: str, required_sections: list = None) -> dict:
        """
        Deterministic check: verify if the response contains required markdown sections (headers).
        Default sections mimic a Triage report.
        """
        if required_sections is None:
            required_sections = ["Summary", "Evidence", "Next Steps"]
            
        if not response:
            return {"score": 0.0, "missing": required_sections}
            
        missing = []
        # Normalizing to verify presence of "## Summary" or "**Summary**" or just "Summary:"
        # A simple check is looking for the keyword roughly as a header or bold
        lower_resp = response.lower()
        
        for section in required_sections:
            # Look for "section" followed by newline or colon, loose match
            if section.lower() not in lower_resp:
                missing.append(section)
        
        score = 1.0 - (len(missing) / len(required_sections))
        return {"score": max(0.0, score), "missing": missing}

    @staticmethod
    def grade_evidence_citation(response: str, context: str, threshold: int = 1) -> float:
        """
        Deterministic check: verify if strings from the 'context' appear in the 'response'.
        This is a proxy for "Did it use the provided log lines?".
        
        Strategy:
        1. Extract specific identifiers from context (like timestamps, error codes, request IDs).
        2. Check if they appear in the response.
        
        For this demo, we'll do a simpler check:
        - Split context into lines.
        - If a line matches a "log format" (timestamp etc), treat it as a critical finding.
        - Check if that finding's key substrings appear in response.
        """
        if not context or not response:
            return 0.0
            
        # 1. Identify "evidence" candidates in context. 
        # Assume context is a list of log lines or a text blob of logs.
        context_lines = context.split('\n')
        # Filter for lines that look like logs (have a timestamp-ish or keywords)
        evidence_candidates = [line for line in context_lines if len(line.strip()) > 20]
        
        if not evidence_candidates:
            return 1.0 # No evidence to cite, so N/A (pass)
            
        hits = 0
        # Check a sample of candidates to avoid heavy compute on huge logs
        sample_size = min(len(evidence_candidates), 10)
        import random
        # We want deterministic scoring for the same input, so we sort then pick, or just pick first N
        # Let's pick first N longest lines (likely most distinct)
        evidence_candidates.sort(key=len, reverse=True)
        sample = evidence_candidates[:sample_size]
        
        for line in sample:
            # We don't expect exact line match (formatting diffs).
            # We look for significant substrings (e.g. 5 consecutive words)
            words = line.split()
            if len(words) < 5: 
                continue
                
            # Create a localized signature (e.g. 3 middle words)
            mid = len(words) // 2
            signature = " ".join(words[mid-1:mid+2]).lower()
            
            if signature in response.lower():
                hits += 1
                
        # If we found at least 'threshold' citations, we give full marks? 
        # Or proportional? Let's be strict: if we have evidence, we want to see it used.
        # But 'context' might contain irrelevant logs too.
        # Let's assume if we find > 0 hits, it's good.
        
        return 1.0 if hits >= threshold else 0.0

    @staticmethod
    def grade_routing(trace: list, expected_tool: str) -> float:
        """
        Deterministic check: verify if the expected tool was called in the trace.
        
        Args:
            trace: List of dicts representing the execution trace.
            expected_tool: string identifier for the tool (e.g., 'sql_tool', 'rag_tool').
            
        Returns:
            1.0 if the tool was found, 0.0 otherwise.
        """
        if not trace or not expected_tool:
            return 0.0
            
        # Normalize tool names if needed.
        # Check if any Step in the trace has this tool.
        # Trace format: [{"type": "ai", "tool_calls": [...]}, ...]
        
        for step in trace:
            # Check for direct tool calls in AI messages
            if step.get("type") == "ai" and "tool_calls" in step:
                for call in step["tool_calls"]:
                    # tool_calls structure depends on the framework, assume dict with 'name'
                    if isinstance(call, dict) and call.get("name") == expected_tool:
                        return 1.0
                    # If it's an object, we might need getattr; assuming serialized dict here
            
            # Check for "tool" messages which imply the tool was executed
            if step.get("type") == "tool" and step.get("name") == expected_tool:
                return 1.0
                
            # Fallback: check content for raw string match if trace is messy
            # (Use with caution)
            
        return 0.0
