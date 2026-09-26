"""Explicitly scoped, additive geometry modifications for human review."""
import numpy as np
import trimesh
import manifold3d as md
from .pipeline import boolean,box_between,inspect_mesh

def fill_local_undercut(mesh,bounds,axis='Y',padding_mm=.00002):
    """Fill gaps along an axis ONLY inside the supplied selection box.

    Intersect opposite directional sweeps to get the interval hull, then clip
    the added material to the selection. The original mesh is not mutated.
    The thin Minkowski kernel uses explicit numerical padding, not a print fit.
    """
    bounds=np.asarray(bounds,dtype=float)
    if bounds.shape!=(2,3) or not np.isfinite(bounds).all() or np.any(bounds[1]<=bounds[0]):raise ValueError('Supply finite increasing 3D selection bounds')
    if axis not in 'XYZ' or len(axis)!=1:raise ValueError('Axis must be X, Y or Z')
    if not mesh.is_volume:raise ValueError('A valid closed input solid is required')
    if not np.isfinite(padding_mm) or padding_mm<=0:raise ValueError('Positive finite numerical padding required')
    i='XYZ'.index(axis);length=float(mesh.extents[i]*2+1)
    solid=md.Manifold(md.Mesh(np.asarray(mesh.vertices,dtype=np.float32),np.asarray(mesh.faces,dtype=np.uint32)))
    if solid.status()!=md.Error.NoError:raise ValueError('Input is not a valid Manifold solid')
    dimensions=np.full(3,padding_mm);dimensions[i]=length
    centre=np.full(3,-padding_mm/2);centre[i]=0
    forward=md.Manifold.cube(dimensions.tolist()).translate(centre.tolist())
    centre[i]=-length
    backward=md.Manifold.cube(dimensions.tolist()).translate(centre.tolist())
    hull=solid.minkowski_sum(forward)^solid.minkowski_sum(backward)
    if hull.status()!=md.Error.NoError:raise ValueError('Directional fill failed')
    selection=md.Manifold.cube((bounds[1]-bounds[0]).tolist()).translate(bounds[0].tolist())
    edited=(solid+(hull^selection)).simplify(.0001)
    raw=edited.to_mesh64()
    result=trimesh.Trimesh(raw.vert_properties[:,:3],raw.tri_verts,process=True)
    if not result.is_volume:raise ValueError('Local edit did not produce a valid closed solid')
    return result,{'operation':'fill_local_undercut','selection_bounds_mm':bounds.tolist(),'axis':axis,
                   'numerical_padding_mm':padding_mm,'cleanup_tolerance_mm':.0001,'added_volume_mm3':float(result.volume-mesh.volume),
                   'input':inspect_mesh(mesh),'output':inspect_mesh(result),
                   'scope':'Only material within the selected box may be added. Recheck release after editing.'}


def lower_tip_smoothly(mesh, start_x_mm, end_x_mm, drop_mm):
    """Lower a +X feature using a C2 quintic transition and rigid tip translation.

    Select the interval outside the body. X/Y stay fixed; Z is shifted by a
    function of X, so the continuous map is invertible. The triangulated mesh
    still needs validation. No tip clipping or invented pouring opening.
    """
    if not np.isfinite([start_x_mm,end_x_mm,drop_mm]).all() or end_x_mm<=start_x_mm or drop_mm<=0:
        raise ValueError('Increasing finite X interval and positive drop required')
    result=mesh.copy()
    t=np.clip((result.vertices[:,0]-start_x_mm)/(end_x_mm-start_x_mm),0,1)
    weight=t*t*t*(10+t*(-15+6*t))
    result.vertices[:,2]-=drop_mm*weight
    return result


def apply_feature_edits(mesh, edits):
    """Apply separately authorized feature edits, validating actual STL round trips.

    Decisions belong to individual regions; permission for one feature never
    authorizes another. Keep the original immutable for visual review.
    """
    import io
    if not mesh.is_volume or not edits:raise ValueError('Closed input and feature decisions required')
    for edit in edits:
        if not edit.get('feature') or edit.get('choice')!='simplify' or not edit.get('authorization','').strip():
            raise ValueError('Each edited feature needs its own simplify decision and authorization')
    result=mesh.copy(); reports=[]
    for edit in edits:
        before=result.volume
        if edit['operation']=='smooth_local_patch':
            result,_=smooth_local_patch(result,edit['center_mm'],edit['radii_mm'],edit.get('iterations',30),edit.get('max_displacement_mm',.3))
        elif edit['operation']=='fill_local_undercut':
            result,_=fill_local_undercut(result,edit['bounds'],edit.get('axis','Y'),edit.get('padding_mm',.00002))
        elif edit['operation']=='lower_tip_smoothly':
            result=lower_tip_smoothly(result,edit['start_x_mm'],edit['end_x_mm'],edit['drop_mm'])
        elif edit['operation']=='trim_max':
            axis=edit['axis'];position=float(edit['position_mm'])
            if axis not in ('X','Y','Z') or not np.isfinite(position):raise ValueError('Invalid trim plane')
            i='XYZ'.index(axis);lo=result.bounds[0]-1;hi=result.bounds[1]+1
            if not result.bounds[0,i]<position<result.bounds[1,i]:raise ValueError('Trim must cross the object')
            hi[i]=position; result=boolean('intersection',[result,box_between(lo,hi)])
        elif edit['operation']=='add_frustum':
            z=np.asarray(edit['z_mm'],float);r=np.asarray(edit['radius_mm'],float);xy=np.asarray(edit['center_xy'],float)
            if z.shape!=(2,) or r.shape!=(2,) or xy.shape!=(2,) or not np.isfinite(np.r_[z,r,xy]).all() or z[1]<=z[0] or np.any(r<=0):raise ValueError('Invalid collar dimensions')
            collar=trimesh.creation.revolve([[0,z[0]],[r[0],z[0]],[r[1],z[1]],[0,z[1]]],sections=192)
            collar.apply_translation([*xy,0]);result=boolean('union',[result,collar])
        else:raise ValueError('Unsupported feature edit')
        result=trimesh.load_mesh(io.BytesIO(result.export(file_type='stl')),file_type='stl')
        if not result.is_volume:raise ValueError('Edited STL failed closed-solid validation')
        reports.append({**edit,'volume_change_mm3':float(result.volume-before)})
    return result,{'features':reports,'input':inspect_mesh(mesh),'output':inspect_mesh(result),'scope':'Proposed source edits; input review and release checks required.'}


def smooth_local_patch(mesh,center_mm,radii_mm,iterations=30,max_displacement_mm=.3):
    """Bounded Laplacian smoothing with a fixed, softly weighted ellipsoid mask.

    Vertices outside the original selection are unchanged. This creates a
    proposal, not a release guarantee; inspect distortion and export validity.
    """
    from scipy.sparse import coo_matrix
    center=np.asarray(center_mm,float);radii=np.asarray(radii_mm,float)
    if center.shape!=(3,) or radii.shape!=(3,) or not np.isfinite(np.r_[center,radii]).all() or np.any(radii<=0):raise ValueError('Finite center and positive radii required')
    if not isinstance(iterations,int) or iterations<1 or not np.isfinite(max_displacement_mm) or max_displacement_mm<=0:raise ValueError('Positive iteration count and displacement limit required')
    if not mesh.is_volume:raise ValueError('Closed input required')
    original=mesh.vertices.copy();result=mesh.copy()
    distance=np.linalg.norm((original-center)/radii,axis=1)
    t=np.clip(1-distance,0,1);weight=t*t*(3-2*t)
    edges=mesh.edges_unique;row=np.r_[edges[:,0],edges[:,1]];col=np.r_[edges[:,1],edges[:,0]]
    degree=np.bincount(row,minlength=len(original))
    averaging=coo_matrix((1/degree[row],(row,col)),shape=(len(original),len(original))).tocsr()
    vertices=original.copy()
    for _ in range(iterations):
        vertices+=.5*weight[:,None]*(averaging@vertices-vertices)
        delta=vertices-original;length=np.linalg.norm(delta,axis=1)
        vertices=original+delta*np.minimum(1,max_displacement_mm/np.maximum(length,1e-30))[:,None]
    result.vertices=vertices
    displacement=np.linalg.norm(vertices-original,axis=1)
    if not result.is_volume:raise ValueError('Smoothing produced invalid solid')
    return result,{'operation':'smooth_local_patch','center_mm':center.tolist(),'radii_mm':radii.tolist(),'iterations':iterations,'displacement_limit_mm':max_displacement_mm,'max_displacement_mm':float(displacement.max()),'moved_vertices':int(np.count_nonzero(displacement>0)),'outside_selection_max_displacement_mm':float(displacement[distance>=1].max(initial=0)),'scope':'Only vertices inside the original ellipsoid move. Release and STL checks still required.'}
