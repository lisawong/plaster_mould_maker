"""Reusable geometry operations. All mesh coordinates are millimetres."""
from pathlib import Path
import numpy as np
import trimesh


def inspect_mesh(mesh):
    counts = np.bincount(mesh.edges_unique_inverse)
    return dict(dimensions_mm=mesh.extents.tolist(), volume_mm3=float(mesh.volume),
                nonmanifold_edges=int(np.count_nonzero(counts != 2)),
                watertight=bool(mesh.is_watertight), winding_consistent=bool(mesh.is_winding_consistent),
                vertices=len(mesh.vertices), triangles=len(mesh.faces))


def prepare_stl(path, target_mm, scale_axis='Y'):
    if scale_axis not in ('X','Y','Z') or not np.isfinite(target_mm) or target_mm <= 0:
        raise ValueError('Specify a positive finite target dimension and X/Y/Z scale axis')
    mesh = trimesh.load_mesh(str(Path(path)), process=True)
    if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces)==0:
        raise ValueError('Input must contain a triangle mesh')
    if not np.isfinite(mesh.vertices).all() or not mesh.is_watertight:
        raise ValueError('Input must be finite and watertight; repair explicitly before mould design')
    mesh.fix_normals(multibody=True)
    width = mesh.extents['XYZ'.index(scale_axis)]
    if width <= 0:
        raise ValueError('Input has zero extent on the scale axis')
    mesh.apply_scale(target_mm / width)
    mesh.apply_translation(-mesh.bounds.mean(axis=0))
    from .intersections import find_edge_face_crossings
    crossing_report=find_edge_face_crossings(mesh)
    if crossing_report['crossing_count']:
        raise ValueError(f"Input has {crossing_report['crossing_count']} strict edge-face crossings; repair explicitly before mould design")
    report=inspect_mesh(mesh)
    report['strict_edge_face_crossings']=0
    report['intersection_check_limitation']=crossing_report['limitation']
    return mesh, report


def box_between(lo, hi):
    lo=np.asarray(lo,dtype=float); hi=np.asarray(hi,dtype=float)
    mesh=trimesh.creation.box(hi-lo); mesh.apply_translation((lo+hi)/2)
    return mesh


def solid_volume(mesh):
    """Signed enclosed volume in mm3 via the divergence theorem.

    trimesh's ``volume`` goes through mass properties, which divide by the volume for
    the centre of mass; zero-thickness Boolean results (touching solids) then raise
    divide-by-zero RuntimeWarnings. This computes the volume alone.
    """
    if not len(mesh.faces):
        return 0.
    t=mesh.triangles
    return float(np.einsum('ij,ij->i',t[:,0],np.cross(t[:,1],t[:,2])).sum()/6)


def is_solid(mesh):
    """trimesh's ``is_volume`` without its centre-of-mass step, which warns on zero-volume
    closed fragments. Closed, consistently wound and positive volume."""
    return bool(len(mesh.faces) and mesh.is_watertight and mesh.is_winding_consistent and solid_volume(mesh)>0)


def boolean(op, meshes):
    return getattr(trimesh.boolean,op)(meshes,engine='manifold')


def build_tooling(mesh, margin=12, backing=12, gate_radius=5):
    """Candidate split along Y=0. Release validation is a separate required step.

    Plaster meshes use assembled coordinates. Master meshes use local pour-up Y.
    Printed side walls are shared between masters and removed before demoulding.
    """
    low, high=mesh.bounds
    if not (low[1]<0<high[1]):
        raise ValueError('The parting plane Y=0 must pass through the object')
    x0,x1=low[0]-margin,high[0]+margin
    z0,z1=low[2]-margin,high[2]+margin
    depth=max(-low[1],high[1])+backing
    gate=trimesh.creation.cylinder(radius=gate_radius,height=margin+4,sections=64)
    # Gate enters the centre of the base; it is the slip fill/drain opening.
    gate.apply_translation([0,0,z0+(margin+4)/2-1])
    cavity=boolean('union',[mesh,gate])
    plus=boolean('difference',[box_between([x0,0,z0],[x1,depth,z1]),cavity])
    minus=boolean('difference',[box_between([x0,-depth,z0],[x1,0,z1]),cavity])
    # Two smooth hemispherical keys, safely outside the object's silhouette.
    keys=[]
    for x,z in [(x0+6,z1-6),(x1-6,z0+6)]:
        key=trimesh.creation.icosphere(subdivisions=3,radius=2.5); key.apply_translation([x,0,z]); keys.append(key)
    # Male keys on minus, matching sockets in plus.
    minus=boolean('union',[minus,*[boolean('intersection',[k,box_between([x0,0,z0],[x1,depth,z1])]) for k in keys]])
    plus=boolean('difference',[plus,*keys])
    masters=[]
    for plaster,sign in [(plus,1),(minus,-1)]:
        p=plaster.copy()
        if sign==-1:
            p.apply_transform(np.diag([1,-1,1,1]))
        # Complement of plaster in a slab: positive pattern above its backing plate.
        # Keep just central pattern and extended base; walls are separate pieces.
        core=boolean('difference',[box_between([x0,-4,z0],[x1,depth,z1]),p])
        base=boolean('difference',[box_between([x0-4,-4,z0-4],[x1+4,0,z1+4]),
                                   box_between([x0,-5,z0],[x1,1,z1])])
        masters.append(boolean('union',[core,base]))
    # Four butt-jointed panels. Long panels span width including the end panels.
    walls=[box_between([x0-3,0,z0-3],[x1+3,depth,z0]),
           box_between([x0-3,0,z1],[x1+3,depth,z1+3]),
           box_between([x0-3,0,z0],[x0,depth,z1]),
           box_between([x1,0,z0],[x1+3,depth,z1])]
    return dict(plaster=[plus,minus],masters=masters,walls=walls,cavity=cavity,
                bounds=[x0,x1,z0,z1],depth=depth,gate_radius=gate_radius)


def check_release(moving, fixed, direction, distances, tolerance_mm3=0.001):
    """Sampled solid intersections; NOT a continuous swept-volume proof."""
    direction=np.asarray(direction,dtype=float)
    if direction.shape!=(3,) or not np.isfinite(direction).all() or np.linalg.norm(direction)==0:
        raise ValueError('Supply a finite nonzero direction')
    direction/=np.linalg.norm(direction)
    samples=[]
    for distance in distances:
        shifted=moving.copy(); shifted.apply_translation(direction*distance)
        intersection=boolean('intersection',[shifted,fixed])
        volume=max(0.,solid_volume(intersection))
        samples.append(dict(distance_mm=float(distance),intersection_mm3=volume))
    return dict(passed=all(s['intersection_mm3']<=tolerance_mm3 for s in samples),
                tolerance_mm3=tolerance_mm3,samples=samples,
                limitation='Discrete positions only; does not prove continuous collision-free motion or physical release.')


def partition_with_top_cap(mesh,split_z,core_radius,core_x=0,margin=12,backing=12,gate_radius=5):
    result=build_tooling(mesh,margin,backing,gate_radius)
    x0,x1,z0,z1=result['bounds']; depth=result['depth']
    upper=box_between([x0,-depth,split_z],[x1,depth,z1])
    core=trimesh.creation.cylinder(radius=core_radius,height=z1-split_z+2,sections=128)
    core.apply_translation([core_x,0,(split_z+z1)/2])
    cap_region=boolean('difference',[upper,core])
    cap=boolean('difference',[cap_region,result['cavity']])
    lower=[boolean('difference',[p,cap_region]) for p in result['plaster']]
    result['plaster']=[*lower,cap]
    result['cap_region']=cap_region
    # Two-part masters do not cast these newly partitioned parts.
    result['masters']=[]
    result['walls']=[]
    return result


def partition_local_insert(mesh, selection_bounds, **tooling_settings):
    """Separate an explicitly selected local region from both main halves.

    Selection and removal order require review. Existing two-part casting forms
    are withheld because they do not cast this new partition.
    """
    bounds=np.asarray(selection_bounds,dtype=float)
    if bounds.shape!=(2,3) or not np.isfinite(bounds).all() or np.any(bounds[1]<=bounds[0]):
        raise ValueError('Finite increasing selection bounds required')
    result=build_tooling(mesh,**tooling_settings)
    region=box_between(*bounds)
    selected=[boolean('intersection',[part,region]) for part in result['plaster']]
    insert=boolean('union',selected)
    lower=[boolean('difference',[part,region]) for part in result['plaster']]
    if not all(part.is_volume for part in [*lower,insert]):raise ValueError('Selection must produce valid solid parts')
    result.update(plaster=[*lower,insert],masters=[],walls=[],insert_bounds=bounds.tolist())
    return result
