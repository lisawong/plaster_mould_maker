"""Versioned result record every CLI command prints (PRD R9.1)."""
from pathlib import PurePosixPath
from typing import Any, Literal, get_args

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

SCHEMA_VERSION = 'mouldflow.result/1'

Outcome = Literal['strict_pass', 'conditional_finishing', 'inconclusive', 'fail', 'unsupported']
OUTCOMES = get_args(Outcome)
# Outcomes a human may approve; everything else must be resolved first.
APPROVABLE = ('strict_pass', 'conditional_finishing')


class Metric(BaseModel):
    """A number with its unit and whether it is a measurement or a bound. Depth (mm) is never volume (mm3)."""
    model_config = ConfigDict(extra='forbid', frozen=True)
    value: float
    unit: Literal['mm', 'mm2', 'mm3', 'count', 'ratio', 'deg']
    kind: Literal['measured', 'lower_bound', 'upper_bound']


def check_relative(path):
    """Reject absolute paths and paths that escape the job folder."""
    p = PurePosixPath(str(path).replace('\\', '/'))
    if p.is_absolute() or '..' in p.parts or not p.parts:
        raise ValueError(f'path must be relative to the job folder: {path}')
    return p.as_posix()


class ResultRecord(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_version: Literal['mouldflow.result/1'] = SCHEMA_VERSION
    command: str
    status: Literal['ok', 'error']
    stage: str | None = None
    outcome: Outcome | None = None
    metrics: dict[str, Metric] = {}
    limitations: list[str] = []
    next_action: str | None = None
    evidence: list[str] = []
    hashes: dict[str, str] = {}
    details: dict[str, Any] = {}
    error: str | None = None

    @field_validator('evidence')
    @classmethod
    def _relative_evidence(cls, paths):
        return [check_relative(p) for p in paths]

    @model_validator(mode='after')
    def _error_matches_status(self):
        if (self.status == 'error') != bool(self.error):
            raise ValueError('error message is required for status "error" and forbidden otherwise')
        return self
