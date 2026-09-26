"""Generate review candidates, never silently promote them to fabrication-ready."""
import argparse, hashlib, json
from pathlib import Path
import numpy as np
from .pipeline import prepare_stl,build_tooling,partition_with_top_cap,check_release,inspect_mesh

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stl',type=Path);parser.add_argument('--config',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--workflow',type=Path,help='Use persisted human review gates; otherwise generate diagnostic candidates only')
    args=parser.parse_args();settings=json.loads(args.config.read_text())
    flow=None
    if args.workflow:
        from .workflow import ReviewWorkflow
        flow=ReviewWorkflow(args.workflow);flow.require_approved('input')
        reviewed=flow.status()['input']
        if str(args.stl.resolve()) not in reviewed['files'] or str(args.config.resolve()) not in reviewed['files']:
            raise ValueError('Review the exact input STL and settings file before this run')
    mesh,input_report=prepare_stl(args.stl,settings['target_mm'],settings.get('scale_axis','Y'))
    mode=settings.get('mode','two_part')
    common={k:settings[k] for k in ['margin','backing','gate_radius'] if k in settings}
    if mode=='two_part':
        result=build_tooling(mesh,**common);directions=[[0,1,0],[0,-1,0]]
    elif mode=='top_cap':
        result=partition_with_top_cap(mesh,**settings['top_cap'],**common);directions=[[0,1,0],[0,-1,0],[0,0,1]]
    else: raise ValueError('Unsupported partition mode')
    if flow:
        # Plaster design review must precede printable-form generation.
        result['masters']=[];result['walls']=[]
    args.out.mkdir(parents=True,exist_ok=True)
    if (args.out/'report.json').exists(): raise ValueError('Output already contains a run; choose a new output directory')
    (args.out/'settings.json').write_text(json.dumps(settings,indent=2))
    mesh.export(args.out/'prepared_object.stl')
    steps=settings.get('release_samples_mm',[0,.1,.25,.5,1,2,4,8,16,32,64])
    if not steps or any(not np.isfinite(x) or x<0 for x in steps):raise ValueError('Release samples must be finite, nonnegative distances')
    report=dict(status='in_progress',print_ready=False,input=input_report,
                source_sha256=hashlib.sha256(args.stl.read_bytes()).hexdigest(),
                units='mm',mode=mode,parts={},release={},
                limitations=['Sampled positions are not a continuous swept-volume proof.',
                'No physical release, print finish, or plaster strength validation.',
                'Top-cap mode is plaster design only; its casting forms are not generated.'])
    for group,folder in [('plaster','reference_plaster'),('masters','print_candidates'),('walls','print_candidates')]:
        (args.out/folder).mkdir(exist_ok=True)
        for i,part in enumerate(result[group]):
            name=f'{group.rstrip("s")}_{i+1}';path=args.out/folder/f'{name}.stl';part.export(path)
            # Verify the artifact actually written, not only the in-memory solid.
            import trimesh
            reread=trimesh.load_mesh(path)
            part_report=inspect_mesh(reread)
            part_report['fits_mk3_some_orientation']=bool(np.all(np.sort(reread.extents)<=np.sort([250,210,210])))
            report['parts'][name]=part_report
    for i,(part,direction) in enumerate(zip(result['plaster'],directions)):
        report['release'][f'plaster_{i+1}_vs_object']=check_release(part,result['cavity'],direction,steps)
    if mode=='two_part':
        report['release']['first_half_vs_second']=check_release(result['plaster'][0],result['plaster'][1],[0,1,0],steps)
        for i,sign in enumerate([1,-1] if result['masters'] else []):
            plaster=result['plaster'][i].copy()
            if sign==-1:plaster.apply_transform(np.diag([1,-1,1,1]))
            report['release'][f'plaster_{i+1}_vs_printed_master']=check_release(plaster,result['masters'][i],[0,1,0],steps)
    else:
        import trimesh
        lower=trimesh.boolean.union(result['plaster'][:2],engine='manifold')
        report['release']['cap_vs_lower_parts']=check_release(result['plaster'][2],lower,[0,0,1],steps)
    report['status']='candidate_passed_sampled_checks' if all(r['passed'] for r in report['release'].values()) else 'rejected_release_collision'
    (args.out/'report.json').write_text(json.dumps(report,indent=2))
    if flow:
        artifacts=[args.out/'report.json',args.out/'settings.json',args.out/'prepared_object.stl',*sorted((args.out/'reference_plaster').glob('*.stl'))]
        flow.submit('plaster',settings,artifacts,checks_passed=report['status']=='candidate_passed_sampled_checks')
    print(json.dumps({'status':report['status'],'report':str(args.out/'report.json'),'print_ready':False}))

if __name__=='__main__':main()
