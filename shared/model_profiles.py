"""Server-owned, immutable Ollama profiles; callers cannot supply endpoints."""
import hashlib
import json
import os
from pathlib import Path
from typing import Dict, Literal, Optional
from urllib.parse import urlsplit
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ModelSettings(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    model: str = Field(min_length=1, max_length=128, pattern=r'^[A-Za-z0-9][A-Za-z0-9._:/-]*$')
    temperature: float = Field(default=0.1, ge=0, le=2, allow_inf_nan=False)
    top_p: float = Field(default=1.0, gt=0, le=1, allow_inf_nan=False)
    max_tokens: int = Field(default=1024, strict=True, ge=16, le=8192)
    seed: int = Field(default=42, strict=True, ge=0, le=2147483647)
    reasoning_effort: Optional[Literal['none', 'low', 'medium', 'high']] = None

    def request_options(self):
        return self.model_dump(exclude={'model'}, exclude_none=True)


class ModelProfile(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    generation: ModelSettings
    validation: ModelSettings


class ProfileCatalog(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_version: Literal[1]
    api_base: str
    profiles: Dict[str, ModelProfile] = Field(min_length=1, max_length=32)

    @model_validator(mode='after')
    def validate_catalog(self):
        import re
        url = urlsplit(self.api_base)
        if (url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password
                or url.query or url.fragment or not url.path.rstrip('/').endswith('/v1')):
            raise ValueError('Expected a credential-free Ollama v1 endpoint')
        if any(not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', name) for name in self.profiles):
            raise ValueError('Invalid profile ID')
        return self

    def resolve(self, name):
        if name not in self.profiles:
            raise ValueError('Unknown model profile')
        profile = self.profiles[name]
        manifest = {'profile_id': name, 'provider': 'ollama', **profile.model_dump(),
                    'endpoint_sha256': hashlib.sha256(self.api_base.encode()).hexdigest()}
        manifest['profile_sha256'] = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
        return profile, manifest


def load_catalog():
    path = os.getenv('LOGPILOT_MODEL_PROFILES_PATH')
    if not path:
        raise ValueError('Model profiles are not enabled')
    return ProfileCatalog.model_validate_json(Path(path).read_bytes())
