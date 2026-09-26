"""Small-model-friendly review commands; approval records an explicit human decision."""
import argparse,json,sys,hashlib
from pathlib import Path
from .workflow import ReviewWorkflow,ReviewRequired,STAGES

def summary(flow):
    state=flow.status()
    for stage in STAGES:
        pending=[name for name,item in state.get('_features',{}).get(stage,{}).items() if item['choice'] is None]
        if pending:
            return {'next_action':'review_feature','stage':stage,'feature':pending[0],'details':state['_features'][stage][pending[0]],'stages':state}
        record=state.get(stage)
        if record is None:
            action=f'generate_{stage}';break
        if record.get('change_request'):
            action=f'regenerate_{stage}';break
        if not record['approved']:
            action=f'review_{stage}' if record['checks_passed'] else f'resolve_{stage}_checks';break
    else:action='review_complete'
    return {'next_action':action,'stages':state}

def prepare_input(stl,config,out,flow):
    from .pipeline import prepare_stl
    from .preview import render_input
    settings=json.loads(Path(config).read_text())
    mesh,report=prepare_stl(stl,settings['target_mm'],settings.get('scale_axis','Y'))
    out=Path(out)
    if out.exists() and any(out.iterdir()):raise ValueError('Use a new output folder for each input revision')
    out.mkdir(parents=True,exist_ok=True)
    mesh.export(out/'input.stl');(out/'settings.json').write_text(json.dumps(settings,indent=2))
    report['source_sha256']=hashlib.sha256(Path(stl).read_bytes()).hexdigest()
    report['scope']='Input scale and mesh checks only; not mould release validation.'
    (out/'input-report.json').write_text(json.dumps(report,indent=2))
    render_input(mesh,out/'preview.png')
    flow.submit('input',settings,[out/name for name in ['input.stl','settings.json','input-report.json','preview.png']],
                checks_passed=report['watertight'] and report['winding_consistent'] and report['volume_mm3']>0)

def modify_input(source,spec,out,decision,flow):
    import shutil
    import trimesh
    from .simplify import fill_local_undercut
    from .preview import render_input
    flow.require_approved('input')
    parent=flow.status()['input'];source=Path(source).resolve()
    if str(source) not in parent['files']:raise ValueError('Select the reviewed input STL')
    if not decision.strip():raise ValueError('Record the human-authorized edit scope')
    edit=json.loads(Path(spec).read_text())
    if edit.get('operation')!='fill_local_undercut':raise ValueError('Unsupported source modification')
    out=Path(out)
    if out.exists() and any(out.iterdir()):raise ValueError('Use a new folder for a modified input')
    mesh=trimesh.load_mesh(source)
    changed,report=fill_local_undercut(mesh,edit['bounds'],edit.get('axis','Y'))
    out.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,out/'original.stl')
    changed.export(out/'input.stl')
    report.update(parent_revision=parent['revision'],authorization=decision,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    settings={**parent['settings'],'source_edit':edit}
    (out/'settings.json').write_text(json.dumps(settings,indent=2));(out/'edit-report.json').write_text(json.dumps(report,indent=2))
    render_input(changed,out/'preview.png')
    flow.request_changes('input',decision)
    flow.submit('input',settings,[out/n for n in ['original.stl','input.stl','settings.json','edit-report.json','preview.png']],checks_passed=changed.is_volume)

def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    status=sub.add_parser('status');status.add_argument('state')
    approve=sub.add_parser('approve');approve.add_argument('state');approve.add_argument('stage',choices=STAGES)
    approve.add_argument('--revision',required=True);approve.add_argument('--decision',required=True)
    changes=sub.add_parser('changes');changes.add_argument('state');changes.add_argument('stage',choices=STAGES);changes.add_argument('--note',required=True)
    feature=sub.add_parser('feature');feature.add_argument('state');feature.add_argument('stage',choices=STAGES);feature.add_argument('name');feature.add_argument('--region',required=True);feature.add_argument('--issue',required=True)
    decide=sub.add_parser('decide-feature');decide.add_argument('state');decide.add_argument('stage',choices=STAGES);decide.add_argument('name');decide.add_argument('--choice',choices=['simplify','preserve'],required=True);decide.add_argument('--decision',required=True)
    prepare=sub.add_parser('prepare');prepare.add_argument('--stl',required=True);prepare.add_argument('--config',required=True);prepare.add_argument('--state',required=True);prepare.add_argument('--out',required=True)
    modify=sub.add_parser('modify');modify.add_argument('state');modify.add_argument('--source',required=True);modify.add_argument('--spec',required=True);modify.add_argument('--out',required=True);modify.add_argument('--decision',required=True)
    args=parser.parse_args();flow=ReviewWorkflow(args.state)
    try:
        if args.command=='prepare':prepare_input(args.stl,args.config,args.out,flow)
        elif args.command=='modify':modify_input(args.source,args.spec,args.out,args.decision,flow)
        elif args.command=='approve':flow.approve(args.stage,args.revision,args.decision)
        elif args.command=='changes':flow.request_changes(args.stage,args.note)
        elif args.command=='feature':flow.add_feature(args.stage,args.name,args.region,args.issue)
        elif args.command=='decide-feature':flow.decide_feature(args.stage,args.name,args.choice,args.decision)
        print(json.dumps(summary(flow),indent=2))
    except (ReviewRequired,ValueError,KeyError) as error:
        print(json.dumps({'error':str(error),'action':'Inspect status and review the current artifacts.'}),file=sys.stderr)
        raise SystemExit(2)
if __name__=='__main__':main()
