"""Bounded, caller-supplied evaluation context; never a storage/session identity."""
from typing import List, Literal
from pydantic import BaseModel, ConfigDict, Field, RootModel, model_validator


class EvaluationMessage(BaseModel):
    model_config = ConfigDict(extra='forbid')
    role: Literal['user', 'assistant']
    content: str = Field(strict=True, min_length=1, max_length=16000)


class EvaluationContext(RootModel):
    root: List[EvaluationMessage] = Field(max_length=10)

    @model_validator(mode='after')
    def complete_pairs(self):
        if len(self.root) % 2 or any(m.role != ('user' if i % 2 == 0 else 'assistant')
                                   for i, m in enumerate(self.root)):
            raise ValueError('Evaluation context must contain complete user/assistant pairs')
        return self


def validate_cases(cases):
    if not isinstance(cases, list) or not cases or len(cases) > 1000:
        raise ValueError('Expected 1 to 1000 cases')
    seen, turns = set(), {}
    for case in cases:
        if (not isinstance(case, dict) or not isinstance(case.get('id'), str)
                or not case['id'] or case['id'] in seen
                or not isinstance(case.get('question'), str) or not case['question']):
            raise ValueError('Invalid or duplicate case')
        seen.add(case['id'])
        if 'conversation_id' in case or 'turn_index' in case:
            conversation = case.get('conversation_id')
            turn = case.get('turn_index')
            if (not isinstance(conversation, str) or not 1 <= len(conversation) <= 128
                    or type(turn) is not int or turn != turns.get(conversation, 0) + 1
                    or len(case['question']) > 16000):
                raise ValueError('Invalid conversation sequence')
            turns[conversation] = turn
    return cases
