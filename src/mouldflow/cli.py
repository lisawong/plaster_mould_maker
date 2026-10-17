"""mouldflow command line. Every `job` command prints one versioned JSON result record.

`mouldflow job init DIR`      create a job folder with settings, state and artifact folders
`mouldflow job status DIR`    reverify hashes and report every gate and the next action
`mouldflow job decide DIR GATE --revision R --answer approve|request_changes --note TEXT`
                              record an explicit human decision on a pending gate
`mouldflow view MESH[=LABEL]... --out DIR`
                              render views.png, sections.png and a rotatable viewer.html

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
from .view import DEFAULT_VIEWS, MAX_PREVIEW_FACES, VIEWS, ViewError, inspect


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
    view = groups.add_parser('view', help='render PNG views, sections and an HTML viewer of meshes',
                             formatter_class=argparse.RawDescriptionHelpFormatter,
                             epilog='views (with --up z; other up axes rotate x -> y -> z):\n' +
                                    '\n'.join(f'  {name:9} {how}' for name, (_, _, how) in VIEWS.items()) +
                                    '\n\n--explode moves parts apart in views.png and viewer.html only; '
                                    'sections, bounds and marks stay in the assembled pose.')
    view.add_argument('meshes', nargs='+', help='mesh files, optionally PATH=LABEL')
    view.add_argument('--out', type=Path, required=True, help='folder for views.png, sections.png, viewer.html')
    view.add_argument('--section', action='append', default=[], metavar='AXIS=MM',
                      help='cross-section plane (repeatable; default: through the scene centre on x, y, z)')
    view.add_argument('--explode', metavar='AXIS=MM', help='push parts apart from the scene centre along AXIS')
    view.add_argument('--mark', action='append', default=[], metavar='X0,Y0,Z0,X1,Y1,Z1',
                      help='highlight a box in mm (repeatable)')
    view.add_argument('--marks-from', action='append', default=[], type=Path, metavar='RECORD.json',
                      help='highlight worst_location from a release assessment or its result record')
    view.add_argument('--up', choices=('x', 'y', 'z'), default='z', help='axis drawn vertically (default z)')
    view.add_argument('--views', default=','.join(DEFAULT_VIEWS), metavar='NAME,...',
                      help=f'views for views.png (default {",".join(DEFAULT_VIEWS)}; see below)')
    view.add_argument('--title')
    view.add_argument('--no-html', action='store_true', help='skip viewer.html')
    view.add_argument('--max-preview-faces', type=int, default=MAX_PREVIEW_FACES,
                      help='decimate larger meshes for the PNG views only')
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


def _view(args):
    return inspect(args.meshes, args.out, sections=args.section, explode_spec=args.explode, marks=args.mark,
                   marks_from=args.marks_from, up=args.up, title=args.title, html_viewer=not args.no_html,
                   max_preview_faces=args.max_preview_faces,
                   views=[v.strip() for v in args.views.split(',') if v.strip()])


def run(argv):
    args = _parser().parse_args(argv)
    if args.group == 'view':
        try:
            return 0, _view(args)
        except (ViewError, OSError, ValueError) as error:
            return 2, ResultRecord(command='view', status='error', error=str(error),
                                   next_action='Fix the reported mesh path or option and rerun `mouldflow view`.')
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
    if argv and argv[0] not in ('job', 'view', '-h', '--help'):
        from .__main__ import main as prototype_main
        sys.argv = [sys.argv[0], *argv]
        return prototype_main()
    code, record = run(argv)
    print(record.model_dump_json(indent=2))
    raise SystemExit(code)


if __name__ == '__main__':
    main()
