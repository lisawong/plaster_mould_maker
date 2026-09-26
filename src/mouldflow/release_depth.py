"""Linear penetration-depth bounds for discrete collision solids.

For each collision component, bound distance on its boundary, then add half
its smallest enclosing-box thickness to cover its interior (distance is
1-Lipschitz). This is a spatial bound, not a continuous-motion certificate.
"""
import numpy as np
import trimesh
from .pipeline import boolean

def _boundary_bound(triangles,reference,tolerance):
    pending=triangles;measured=0.;settled=0.;last_upper=0.
    for _ in range(12):
        unresolved=[];last_upper=0.
        for start in range(0,len(pending),512):
            t=pending[start:start+512];centers=t.mean(axis=1)
            _,distance,face=trimesh.proximity.closest_point(reference,centers)
            measured=max(measured,float(distance.max(initial=0)))
            ref=np.repeat(reference.triangles[face],3,axis=0)
            closest=trimesh.triangles.closest_point(ref,t.reshape(-1,3))
            upper=np.linalg.norm(closest-t.reshape(-1,3),axis=1).reshape(-1,3).max(axis=1)
            # Distance to a chosen convex reference triangle is convex, so its
            # vertex maximum bounds distance over the complete query triangle.
            done=upper<=measured+tolerance
            settled=max(settled,float(upper[done].max(initial=0)))
            if np.any(~done):unresolved.append(t[~done]);last_upper=max(last_upper,float(upper[~done].max()))
        if not unresolved:return measured, max(settled,last_upper)
        t=np.concatenate(unresolved);a=t[:,0];b=t[:,1];c=t[:,2];ab=(a+b)/2;bc=(b+c)/2;ca=(c+a)/2
        pending=np.concatenate([np.stack([a,ab,ca],axis=1),np.stack([ab,b,bc],axis=1),np.stack([ca,bc,c],axis=1),np.stack([ab,bc,ca],axis=1)])
        if len(pending)>250000:break
    return measured,max(settled,last_upper)

def collision_depth_bound(collision,reference,spatial_tolerance_mm=.02):
    if not np.isfinite(spatial_tolerance_mm) or spatial_tolerance_mm<=0:raise ValueError('Positive finite spatial tolerance required')
    if not len(collision.faces):return {'measured_depth_mm':0.,'upper_bound_mm':0.,'components':[]}
    components=[];contact_fragments=0
    for component in collision.split(only_watertight=False):
        if np.linalg.matrix_rank(component.vertices-component.vertices.mean(axis=0),tol=1e-10)<3:
            contact_fragments+=1
            continue
        enclosure='original_component'
        if not component.is_volume:
            try:
                component=component.convex_hull
                enclosure='convex_enclosure_of_fragment'
            except Exception as error:
                if np.linalg.matrix_rank(component.vertices-component.vertices.mean(axis=0),tol=1e-10)>=3:
                    raise ValueError('Cannot construct a conservative collision enclosure') from error
                measured,boundary=_boundary_bound(component.triangles,reference,spatial_tolerance_mm)
                components.append({'measured_boundary_depth_mm':measured,'boundary_upper_bound_mm':boundary,'interior_cover_radius_mm':0.,'upper_bound_mm':boundary,'bounds_mm':component.bounds.tolist(),'enclosure':'lower_dimensional_contact'})
                continue
        measured,boundary=_boundary_bound(component.triangles,reference,spatial_tolerance_mm)
        try:_,extents=trimesh.bounds.oriented_bounds(component);thickness=float(min(min(extents),min(component.extents)))
        except Exception:thickness=float(min(component.extents))
        components.append({'enclosure':enclosure,'measured_boundary_depth_mm':measured,'boundary_upper_bound_mm':boundary,'interior_cover_radius_mm':thickness/2,'upper_bound_mm':boundary+thickness/2,'bounds_mm':component.bounds.tolist()})
    return {'measured_depth_mm':max((c['measured_boundary_depth_mm'] for c in components),default=0.),'upper_bound_mm':max((c['upper_bound_mm'] for c in components),default=0.),'components':components,'zero_thickness_contact_fragments':contact_fragments}

def check_release_depth(moving,fixed,direction,distances,allowance_mm=.5,spatial_tolerance_mm=.02):
    direction=np.asarray(direction,float);distances=np.asarray(distances,float)
    if direction.shape!=(3,) or not np.isfinite(direction).all() or np.linalg.norm(direction)==0:raise ValueError('Finite nonzero direction required')
    if distances.ndim!=1 or not len(distances) or not np.isfinite(distances).all() or np.any(distances<0):raise ValueError('Nonnegative finite motion samples required')
    if not np.isfinite(allowance_mm) or allowance_mm<=0:raise ValueError('Positive finite allowance required')
    direction/=np.linalg.norm(direction);samples=[]
    for distance in distances:
        shifted=moving.copy();shifted.apply_translation(direction*distance)
        collision=boolean('intersection',[shifted,fixed]);report=collision_depth_bound(collision,fixed,spatial_tolerance_mm)
        samples.append({'distance_mm':float(distance),**report})
    bound=max(s['upper_bound_mm'] for s in samples)
    return {'metric':'Distance of overlapping material below the fixed solid surface, in mm','allowance_mm':allowance_mm,'spatial_tolerance_mm':spatial_tolerance_mm,'max_upper_bound_mm':bound,'within_allowance_at_samples':bound<allowance_mm,'samples':samples,'limitations':['Discrete motion samples only; not a continuous-motion proof.','Depth bounds are penetration measures, not a map of exact material to sand away.','Passing the allowance is conditional on manual finishing; it does not mean collision-free release.']}
