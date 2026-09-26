"""Persistent human review checkpoints bound to exact files and settings."""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path

STAGES=('input','plaster','forms','export')
class ReviewRequired(ValueError):
    pass

class ReviewWorkflow:
    def __init__(self,path):
        self.path=Path(path)
        self.records=json.loads(self.path.read_text()) if self.path.exists() else {}

    def _save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temporary=self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.records,indent=2))
        temporary.replace(self.path)

    def submit(self,stage,settings,artifacts,checks_passed):
        if stage not in STAGES:raise ValueError('Unknown review stage')
        if not artifacts:raise ValueError('A review needs at least one artifact')
        self._invalidate_from(stage)
        files={str(Path(p).resolve()):hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in artifacts}
        content={'settings':settings,'files':files,'checks_passed':bool(checks_passed)}
        revision=hashlib.sha256(json.dumps(content,sort_keys=True).encode()).hexdigest()
        self.records[stage]={**content,'revision':revision,'approved':False,'decision':None}
        self._save()
        return revision

    def _invalidate_from(self,stage):
        for name in STAGES[STAGES.index(stage):]:
            if name in self.records:
                self.records[name]['approved']=False
                self.records[name]['decision']=None
        self._save()

    def _check_files(self):
        for stage in STAGES:
            if stage not in self.records:continue
            for name,digest in self.records[stage]['files'].items():
                path=Path(name)
                if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
                    self._invalidate_from(stage)
                    return

    def require_approved(self,stage):
        self._check_files()
        if not self.records.get(stage,{}).get('approved'):
            raise ReviewRequired(f'{stage}: review and approval required')

    def approve(self,stage,revision,decision):
        pending=[f for f in self.records.get('_features',{}).get(stage,{}).values() if f['choice'] is None]
        if pending:raise ReviewRequired('Review each complex feature before approving this stage')
        for previous in STAGES[:STAGES.index(stage)]:
            self.require_approved(previous)
        self._check_files()
        record=self.records[stage]
        if record.get('change_request'):raise ReviewRequired('Regenerate and submit the requested changes before approval')
        for name,digest in record['files'].items():
            path=Path(name)
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
                raise ReviewRequired('Artifact changed; submit a fresh revision')
        if not record['checks_passed']:raise ReviewRequired('Failed checks must be resolved before approval')
        if not decision.strip():raise ValueError('Record the human review decision')
        if revision!=record['revision']:raise ReviewRequired('Review revision is stale')
        record.update(approved=True,decision=decision)
        self.records.setdefault('_history',[]).append({'event':'approved','stage':stage,'revision':revision,'decision':decision,'time':datetime.now(timezone.utc).isoformat()})
        self._save()

    def request_changes(self,stage,note):
        if stage not in STAGES or stage not in self.records:raise ValueError('Submit the stage before requesting changes')
        if not note.strip():raise ValueError('Describe the requested change')
        self._invalidate_from(stage)
        self.records[stage]['change_request']=note
        self.records.setdefault('_history',[]).append({'event':'changes_requested','stage':stage,'note':note,'time':datetime.now(timezone.utc).isoformat()})
        self._save()

    def history(self):
        return json.loads(json.dumps(self.records.get('_history',[])))

    def add_feature(self,stage,feature,region,issue):
        if stage not in STAGES or not all([feature,region,issue]):raise ValueError('Stage, feature, region and issue required')
        features=self.records.setdefault('_features',{}).setdefault(stage,{})
        if feature in features:raise ValueError('Feature already registered')
        features[feature]={'region':region,'issue':issue,'choice':None,'decision':None}
        self._invalidate_from(stage)

    def decide_feature(self,stage,feature,choice,decision):
        if choice not in ('simplify','preserve') or not decision.strip():raise ValueError('Choose simplify or preserve and record the human decision')
        record=self.records['_features'][stage][feature]
        record.update(choice=choice,decision=decision)
        self.records.setdefault('_history',[]).append({'event':'feature_decision','stage':stage,'feature':feature,'choice':choice,'decision':decision,'time':datetime.now(timezone.utc).isoformat()})
        if stage in self.records:self.request_changes(stage,f'{feature}: {decision}')
        else:self._save()

    def status(self):
        self._check_files()
        return json.loads(json.dumps(self.records))
