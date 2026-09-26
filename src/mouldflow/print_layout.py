"""Rigid print orientations with an explicit inverse back to assembly space."""
import numpy as np
import trimesh

def print_orientation(mesh,role):
    if not mesh.is_volume:raise ValueError('Closed solid required for print layout')
    if role=='pattern':rotation=trimesh.transformations.rotation_matrix(np.pi/2,[1,0,0])
    elif role=='panel':
        normal=np.eye(3)[int(np.argmin(mesh.extents))]
        rotation=trimesh.geometry.align_vectors(normal,[0,0,1])
    else:raise ValueError('Role must be pattern or panel')
    result=mesh.copy();result.apply_transform(rotation)
    shift=np.array([-result.bounds[:,0].mean(),-result.bounds[:,1].mean(),-result.bounds[0,2]])
    result.apply_translation(shift);translation=np.eye(4);translation[:3,3]=shift
    return result,translation@rotation
