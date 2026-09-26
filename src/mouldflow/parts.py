"""Generic mould parts, release directions and removal order.

Release 1 only generates two-part planar layouts, but the model allows any number of
parts so Release 2 can add multipart moulds without a schema change (SCRATCHPAD A013).
"""
import math
from typing import Literal, NamedTuple

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

Vec3 = tuple[float, float, float]


class Part(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    name: str
    role: Literal['object', 'plaster', 'pattern', 'wall']
    release_direction: Vec3 | None = None

    @field_validator('release_direction')
    @classmethod
    def _unit(cls, v):
        if v is None:
            return v
        length = math.sqrt(sum(c * c for c in v))
        if not math.isfinite(length) or length < 1e-12:
            raise ValueError('release_direction must be finite and nonzero')
        return tuple(c / length for c in v)


class RemovalStep(NamedTuple):
    part: str
    direction: Vec3
    against: tuple[str, ...]  # parts still in place when this one moves


class MouldLayout(BaseModel):
    """`fixed` stays put; every other part is withdrawn once, in `removal_order`."""
    model_config = ConfigDict(extra='forbid', frozen=True)
    parts: list[Part]
    fixed: str
    removal_order: list[str]

    @model_validator(mode='after')
    def _consistent(self):
        names = [p.name for p in self.parts]
        if len(set(names)) != len(names):
            raise ValueError('part names must be unique')
        if self.fixed not in names:
            raise ValueError(f'fixed part {self.fixed!r} is not a part')
        moving = [n for n in names if n != self.fixed]
        if sorted(self.removal_order) != sorted(moving):
            raise ValueError('removal_order must list every non-fixed part exactly once')
        for part in self.parts:
            if part.name != self.fixed and part.release_direction is None:
                raise ValueError(f'part {part.name!r} needs a release_direction')
        return self

    def steps(self):
        by_name = {p.name: p for p in self.parts}
        remaining = [p.name for p in self.parts]
        steps = []
        for name in self.removal_order:
            remaining.remove(name)
            steps.append(RemovalStep(name, by_name[name].release_direction, tuple(remaining)))
        return steps


def two_part_planar(normal):
    """Release 1 layout: plaster_1 withdraws along +normal, then plaster_2 along -normal; object fixed."""
    n = Part(name='_', role='plaster', release_direction=normal).release_direction
    return MouldLayout(parts=[Part(name='object', role='object'),
                              Part(name='plaster_1', role='plaster', release_direction=n),
                              Part(name='plaster_2', role='plaster', release_direction=tuple(-c for c in n))],
                       fixed='object', removal_order=['plaster_1', 'plaster_2'])
