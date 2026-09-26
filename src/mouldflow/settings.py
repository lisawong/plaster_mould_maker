"""Per-job settings. Defaults follow PRD.md; every job stores its own copy in job.json."""
import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, model_validator

SCHEMA_VERSION = 'mouldflow.settings/1'


class _Section(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)


class SourceSettings(_Section):
    """Intake declarations. STL has no units, so `units` stays unset until the human declares it."""
    units: Literal['mm', 'cm', 'm', 'in'] | None = None
    target_mm: PositiveFloat | None = None
    target_axis: Literal['X', 'Y', 'Z'] = 'Y'
    purpose: str | None = None


class PlasterSettings(_Section):
    finishing_allowance_mm: float = Field(0.1, ge=0)
    margin_mm: PositiveFloat = 12
    backing_mm: PositiveFloat = 12
    gate_radius_mm: PositiveFloat = 5
    key_radius_mm: PositiveFloat = 2.5


class FormSettings(_Section):
    wall_thickness_mm: PositiveFloat = 3
    lip_extension_mm: PositiveFloat = 20
    groove_clearance_mm: PositiveFloat = 0.25
    wall_clearance_mm: PositiveFloat = 30
    fill_line_depth_mm: PositiveFloat = 0.6

    @property
    def lip_thickness_mm(self):
        """Lip thickness always equals wall thickness (SCRATCHPAD A019)."""
        return self.wall_thickness_mm

    @model_validator(mode='after')
    def _fill_line_inside_wall(self):
        if self.fill_line_depth_mm >= self.wall_thickness_mm:
            raise ValueError('fill_line_depth_mm must be less than wall_thickness_mm')
        return self


class PrinterSettings(_Section):
    name: str = 'Prusa MK3'
    bed_mm: tuple[PositiveFloat, PositiveFloat, PositiveFloat] = (250, 210, 210)


# Which settings section each review gate is bound to.
GATE_SECTIONS = {'input': 'source', 'plaster': 'plaster', 'forms': 'forms', 'export': 'printer'}


class JobSettings(_Section):
    schema_version: Literal['mouldflow.settings/1'] = SCHEMA_VERSION
    source: SourceSettings = SourceSettings()
    plaster: PlasterSettings = PlasterSettings()
    forms: FormSettings = FormSettings()
    printer: PrinterSettings = PrinterSettings()

    def with_overrides(self, overrides):
        """Return a new validated copy with per-field overrides merged into each section."""
        data = self.model_dump(mode='json')
        for section, values in overrides.items():
            if isinstance(values, dict) and isinstance(data.get(section), dict):
                data[section] = {**data[section], **values}
            else:
                data[section] = values
        return JobSettings.model_validate(data)

    def section_hash(self, section):
        payload = json.dumps(getattr(self, section).model_dump(mode='json'), sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()
