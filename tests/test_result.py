"""Stage 1: versioned result record returned by every command (PRD R9.1)."""
import pytest
from pydantic import ValidationError

from mouldflow.result import OUTCOMES, SCHEMA_VERSION, Metric, ResultRecord


def test_outcomes_are_the_prd_set():
    assert OUTCOMES == ('strict_pass', 'conditional_finishing', 'inconclusive', 'fail', 'unsupported')


def test_record_carries_version_and_round_trips():
    r = ResultRecord(command='job status', status='ok', stage='plaster', outcome='conditional_finishing',
                     metrics={'max_depth': Metric(value=0.04, unit='mm', kind='upper_bound')},
                     limitations=['Sampled positions only.'], next_action='review_plaster',
                     evidence=['candidates/plaster/report.json'], hashes={'source': 'ab' * 32})
    assert r.schema_version == SCHEMA_VERSION == 'mouldflow.result/1'
    assert ResultRecord.model_validate_json(r.model_dump_json()) == r


def test_metric_units_distinguish_depth_from_volume():
    with pytest.raises(ValidationError):
        Metric(value=1, unit='furlong', kind='measured')
    with pytest.raises(ValidationError):
        Metric(value=1, unit='mm', kind='guess')
    assert Metric(value=12, unit='mm3', kind='measured').unit == 'mm3'


@pytest.mark.parametrize('path', ['/abs/report.json', '../outside.stl', 'a/../../b'])
def test_evidence_paths_must_stay_relative_to_the_job(path):
    with pytest.raises(ValidationError):
        ResultRecord(command='x', status='ok', evidence=[path])


def test_error_status_requires_an_error_message_and_ok_forbids_one():
    with pytest.raises(ValidationError):
        ResultRecord(command='x', status='error')
    with pytest.raises(ValidationError):
        ResultRecord(command='x', status='ok', error='boom')
    assert ResultRecord(command='x', status='error', error='boom').error == 'boom'


def test_unknown_outcome_rejected():
    with pytest.raises(ValidationError):
        ResultRecord(command='x', status='ok', outcome='pass')
