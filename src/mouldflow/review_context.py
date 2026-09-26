"""Bind before/after geometry to a located human review, without approval."""
import hashlib
from pathlib import Path
import numpy as np
import trimesh
from scipy.spatial import cKDTree

def review_context(before,after,area_description,tolerance_mm=1e-6):
    if not area_description.strip():raise ValueError('Describe where this is on the whole object')
    old=trimesh.load_mesh(before);new=trimesh.load_mesh(after)
    distance,_=cKDTree(new.vertices).query(old.vertices)
    reverse,_=cKDTree(old.vertices).query(new.vertices)
    changed=old.vertices[distance>tolerance_mm];new_changed=new.vertices[reverse>tolerance_mm]
    points=np.vstack([changed,new_changed])
    if not len(points):raise ValueError('No changed vertices detected at this tolerance')
    return {'area_description':area_description,'before':str(Path(before).resolve()),'after':str(Path(after).resolve()),'before_sha256':hashlib.sha256(Path(before).read_bytes()).hexdigest(),'after_sha256':hashlib.sha256(Path(after).read_bytes()).hexdigest(),'changed_vertex_count':len(changed),'new_changed_vertex_count':len(new_changed),'region_center_mm':points.mean(axis=0).tolist(),'region_bounds_mm':[points.min(axis=0).tolist(),points.max(axis=0).tolist()],'nearest_vertex_change_max_mm':float(max(distance.max(),reverse.max())),'required_views':['whole_object','marked_closeup','before_after','rotatable_3d'],'limitation':'Nearest-vertex differences locate edits; not a surface-distance or release proof.'}
