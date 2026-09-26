"""mouldflow command line. Every `job` command prints one versioned JSON result record.

`mouldflow job init DIR`      create a job folder with settings, state and artifact folders
`mouldflow job status DIR`    reverify hashes and report every gate and the next action
`mouldflow job decide DIR GATE --revision R --answer approve|request_changes --note TEXT`
                              record an explicit human decision on a pending gate

Any other first argument runs the prototype generator (`mouldflow STL --config ... --out ...`).
"""
import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from .job import GATES, Job, JobError
from .result import ResultRecord
from .settings import JobSettings


def _parser():
    parser = argparse.ArgumentParser(prog='mouldflow', description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    groups = parser.add_subparsers(dest='group', required=True)
    job = groups.add_parser('job', help='create and inspect job folders').add_subparsers(dest='command', required=True)
    init = job.add_parser('init', help='create a new job folder')
    init.add_argument('dir', type=Path)
    init.add_argument('--settings', type=Path, help='JSON file of per-section setting overrides')
    init.add_argument('--finishing-allowance-mm', type=float, help='per-job finishing allowance (default 0.1)')
    status = job.add_parser('status', help='reverify hashes and report gates')
    status.add_argument('dir', type=Path)
    decide = job.add_parser('decide', help='record a human decision on a pending gate')
    decide.add_argument('dir', type=Path)
    decide.add_argument('gate', choices=GATES)
    decide.add_argument('--revision', required=True)
    decide.add_argument('--answer', help='approve or request_changes; omitting it never approves')
    decide.add_argument('--note', required=True, help="the human's decision in their words")
    return parser


def _init(args):
    overrides = json.loads(args.settings.read_text()) if args.settings else {}
    if args.finishing_allowance_mm is not None:
        overrides.setdefault('plaster', {})['finishing_allowance_mm'] = args.finishing_allowance_mm
    return Job.init(args.dir, JobSettings().with_overrides(overrides))


def _ok(command, job):
    status = job.status()
    return ResultRecord(command=command, status='ok', next_action=status['next_action'], details=status,
                        evidence=['job.json', 'state.json'])


def run(argv):
    args = _parser().parse_args(argv)
    command = f'{args.group} {args.command}'
    try:
        if args.command == 'init':
            job = _init(args)
        else:
            job = Job.open(args.dir)
            if args.command == 'decide':
                job.decide(args.gate, args.revision, args.answer, args.note)
        return 0, _ok(command, job)
    except (JobError, ValidationError, OSError, ValueError) as error:
        return 2, ResultRecord(command=command, status='error', error=str(error),
                               next_action='Run `mouldflow job status DIR` and follow its next_action; '
                                           'fix the reported input before retrying.')


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] not in ('job', '-h', '--help'):
        from .__main__ import main as prototype_main
        sys.argv = [sys.argv[0], *argv]
        return prototype_main()
    code, record = run(argv)
    print(record.model_dump_json(indent=2))
    raise SystemExit(code)


if __name__ == '__main__':
    main()
