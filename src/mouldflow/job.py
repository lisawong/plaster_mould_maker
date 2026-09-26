"""Job folder and hash-bound review gates (input -> plaster -> forms -> export).

Each gate submission binds exact artifact hashes, the gate's settings section and the
upstream gate's approved revision. Any later mismatch marks the gate and everything
downstream stale. Stale is persisted: restoring bytes or relocating the folder never
turns it back into an approval; only a fresh submission and human decision can.
"""
import hashlib
import json
import os
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path

from .result import APPROVABLE, OUTCOMES, check_relative
from .settings import GATE_SECTIONS, JobSettings

GATES = ('input', 'plaster', 'forms', 'export')
STATE_VERSION = 'mouldflow.state/1'
FOLDERS = ('source', 'candidates', 'reviews', 'approved')
ANSWERS = ('approve', 'request_changes')


class JobError(ValueError):
    pass


class GateBlocked(JobError):
    """The requested transition needs a human decision or a fresh submission first."""


class MissingAnswer(JobError):
    """No explicit human answer was given. A missing answer is never approval."""


class GateStatus(StrEnum):
    NOT_SUBMITTED = 'not_submitted'
    PENDING = 'pending'
    APPROVED = 'approved'
    CHANGES_REQUESTED = 'changes_requested'
    STALE = 'stale'


def _now():
    return datetime.now(timezone.utc).isoformat()


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write_json(path, data):
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(data, indent=2) + '\n')
    os.replace(temporary, path)


class Job:
    def __init__(self, root, settings, state):
        self.root = Path(root)
        self.settings = settings
        self._state = state
        self.relocated = False

    # --- folder -------------------------------------------------------------

    @classmethod
    def init(cls, root, settings=None):
        root = Path(root)
        if root.exists() and (not root.is_dir() or any(root.iterdir())):
            raise JobError(f'{root} is not an empty folder; choose a new job folder')
        settings = settings or JobSettings()
        root.mkdir(parents=True, exist_ok=True)
        for name in FOLDERS:
            (root / name).mkdir()
        job = cls(root, settings, {'schema_version': STATE_VERSION, 'gates': {}, 'history': [],
                                   'last_verified_root': str(root.resolve())})
        _write_json(root / 'job.json', {'settings': settings.model_dump(mode='json')})
        job._event('created')
        return job

    @classmethod
    def open(cls, root):
        root = Path(root)
        if not (root / 'job.json').is_file() or not (root / 'state.json').is_file():
            raise JobError(f'{root} is not a mouldflow job folder; run `mouldflow job init` first')
        try:
            settings = JobSettings.model_validate(json.loads((root / 'job.json').read_text())['settings'])
            state = json.loads((root / 'state.json').read_text())
        except (ValueError, KeyError) as error:
            raise JobError(f'job files are invalid: {error}') from error
        if state.get('schema_version') != STATE_VERSION:
            raise JobError(f'unsupported state version {state.get("schema_version")!r}')
        job = cls(root, settings, state)
        here = str(root.resolve())
        if state.get('last_verified_root') != here:
            # Record the move, then reverify every hash. Intact approvals survive; nothing is re-approved.
            job.relocated = True
            state['last_verified_root'] = here
            job._event('relocated')
        job._verify()
        return job

    def _save(self):
        _write_json(self.root / 'state.json', self._state)

    def _event(self, event, **fields):
        self._state['history'].append({'event': event, 'time': _now(), **fields})
        self._save()

    def update_settings(self, settings):
        """Replace job settings; gates bound to a changed section (and downstream) become stale."""
        self.settings = JobSettings.model_validate(settings.model_dump())
        _write_json(self.root / 'job.json', {'settings': self.settings.model_dump(mode='json')})
        self._event('settings_updated')
        self._verify()

    # --- verification -------------------------------------------------------

    def _artifact_hashes(self, artifacts):
        if not artifacts:
            raise JobError('a gate submission needs at least one artifact')
        hashes = {}
        for item in artifacts:
            try:
                rel = check_relative(item)
            except ValueError as error:
                raise JobError(str(error)) from error
            path = self.root / rel
            if not path.resolve().is_relative_to(self.root.resolve()):
                raise JobError(f'artifact escapes the job folder: {item}')
            if not path.is_file():
                raise JobError(f'artifact not found in job folder: {rel}')
            hashes[rel] = _sha256(path)
        return hashes

    def _stale_reason(self, gate, record):
        for rel, digest in record['artifacts'].items():
            path = self.root / rel
            if not path.is_file():
                return f'artifact missing: {rel}'
            if _sha256(path) != digest:
                return f'artifact changed: {rel}'
        if self.settings.section_hash(GATE_SECTIONS[gate]) != record['settings_hash']:
            return f'settings section {GATE_SECTIONS[gate]!r} changed'
        index = GATES.index(gate)
        if index:
            upstream = self._state['gates'].get(GATES[index - 1])
            if not upstream or upstream['status'] != GateStatus.APPROVED:
                return f'upstream gate {GATES[index - 1]!r} is no longer approved'
            if upstream['revision'] != record['upstream_revision']:
                return f'upstream gate {GATES[index - 1]!r} has a new revision'
        return None

    def _verify(self):
        changed = False
        for gate in GATES:  # upstream first, so invalidation cascades
            record = self._state['gates'].get(gate)
            if not record or record['status'] == GateStatus.STALE:
                continue
            reason = self._stale_reason(gate, record)
            if reason:
                previous = record['status']
                record.update(status=GateStatus.STALE.value, stale_reason=reason, decision=None)
                self._state['history'].append({'event': 'invalidated', 'time': _now(), 'gate': gate,
                                               'revision': record['revision'], 'previous_status': previous,
                                               'reason': reason})
                changed = True
        if changed:
            self._save()

    # --- gates --------------------------------------------------------------

    @staticmethod
    def _check_gate(gate):
        if gate not in GATES:
            raise JobError(f'unknown gate {gate!r}; expected one of {", ".join(GATES)}')

    def gate_status(self, gate):
        self._check_gate(gate)
        self._verify()
        record = self._state['gates'].get(gate)
        return GateStatus(record['status']) if record else GateStatus.NOT_SUBMITTED

    def require_approved(self, gate):
        status = self.gate_status(gate)
        if status is not GateStatus.APPROVED:
            raise GateBlocked(f'{gate}: review and approval required (currently {status})')

    def submit(self, gate, artifacts, outcome, metrics=None, limitations=()):
        """Record a new candidate revision for human review. Returns its revision id."""
        self._check_gate(gate)
        if outcome not in OUTCOMES:
            raise JobError(f'unknown outcome {outcome!r}')
        index = GATES.index(gate)
        upstream_revision = None
        if index:
            self.require_approved(GATES[index - 1])
            upstream_revision = self._state['gates'][GATES[index - 1]]['revision']
        content = {'gate': gate, 'artifacts': self._artifact_hashes(artifacts),
                   'settings_hash': self.settings.section_hash(GATE_SECTIONS[gate]),
                   'upstream_revision': upstream_revision, 'outcome': outcome,
                   'metrics': metrics or {}, 'limitations': list(limitations)}
        revision = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
        self._state['gates'][gate] = {**content, 'revision': revision, 'status': GateStatus.PENDING.value,
                                      'decision': None, 'submitted': _now()}
        self._state['history'].append({'event': 'submitted', 'time': _now(), 'gate': gate,
                                       'revision': revision, 'outcome': outcome})
        self._save()
        self._verify()  # downstream gates bound to the old revision go stale now
        return revision

    def decide(self, gate, revision, answer, note):
        """Record an explicit human answer: 'approve' or 'request_changes'."""
        self._check_gate(gate)
        if answer is None or not str(answer).strip():
            raise MissingAnswer(f'{gate}: no answer recorded; the gate stays pending')
        if answer not in ANSWERS:
            raise JobError(f'answer must be one of {", ".join(ANSWERS)}, got {answer!r}')
        if not note or not note.strip():
            raise JobError('record the human decision in a note')
        status = self.gate_status(gate)
        record = self._state['gates'].get(gate)
        if status is not GateStatus.PENDING:
            raise GateBlocked(f'{gate} is {status}; only a pending submission can be decided')
        if revision != record['revision']:
            raise GateBlocked(f'{gate}: revision {revision!r} is not the current submission')
        if answer == 'approve':
            if record['outcome'] not in APPROVABLE:
                raise GateBlocked(f'{gate}: outcome {record["outcome"]!r} must be resolved before approval')
            record.update(status=GateStatus.APPROVED.value, decision=note)
            self._state['history'].append({'event': 'approved', 'time': _now(), 'gate': gate,
                                           'revision': revision, 'decision': note})
        else:
            record.update(status=GateStatus.CHANGES_REQUESTED.value, decision=None, change_request=note)
            self._state['history'].append({'event': 'changes_requested', 'time': _now(), 'gate': gate,
                                           'revision': revision, 'note': note})
        self._save()
        self._verify()

    # --- reporting ----------------------------------------------------------

    def next_action(self):
        self._verify()
        for gate in GATES:
            record = self._state['gates'].get(gate)
            if not record:
                return f'generate_{gate}'
            status = record['status']
            if status in (GateStatus.STALE, GateStatus.CHANGES_REQUESTED):
                return f'regenerate_{gate}'
            if status == GateStatus.PENDING:
                return f'review_{gate}' if record['outcome'] in APPROVABLE else f'resolve_{gate}_checks'
        return 'complete'

    def history(self):
        return json.loads(json.dumps(self._state['history']))

    def status(self):
        self._verify()
        gates = {}
        for gate in GATES:
            record = self._state['gates'].get(gate)
            gates[gate] = {'status': GateStatus.NOT_SUBMITTED.value} if not record else {
                key: record.get(key) for key in ('status', 'revision', 'outcome', 'decision', 'artifacts',
                                                 'metrics', 'limitations', 'stale_reason', 'change_request')}
        return {'gates': gates, 'next_action': self.next_action(), 'relocated': self.relocated,
                'settings': self.settings.model_dump(mode='json')}
