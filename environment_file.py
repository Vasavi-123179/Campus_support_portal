from typing import Literal

from pydantic import BaseModel


class EnvironmentFile(BaseModel):
    """A live file in an execution environment."""

    environment_id: str
    object: Literal["agent.environment.file"]
    path: str
    size_bytes: int


__all__ = ["EnvironmentFile"]
