"""Candidate height-field parting surface through projected silhouette vertices."""
import io
import numpy as np
import trimesh
from scipy.spatial import Delaunay
from .pipeline import boolean

def contour_seam(candidate,seam_offset_mm=.002):
    if not np.isfinite(seam_offset_mm):raise ValueError("Finite seam offset required")
    mesh=candidate['cavity'];adj=mesh.face_adjacency
    signs=mesh.face_normals[:,1]
    edges=mesh.face_adjacency_edges[(signs[adj[:,0]]*signs[adj[:,1]] < -1e-16)]
    points=mesh.vertices[np.unique(edges)]
    x0,x1,z0,z1=candidate['bounds'];depth=candidate['depth']
    # Keep the outside boundary flat, beyond the cavity silhouette.
    border=np.array([[x,0,z] for x,z in [(x0,z0),(x1,z0),(x1,z1),(x0,z1)]])
    points=np.vstack([points,border]);xz=points[:,[0,2]]
    _,indices,inverse=np.unique(np.round(xz,7),axis=0,return_index=True,return_inverse=True)
    heights=np.zeros(len(indices));counts=np.bincount(inverse)
    np.add.at(heights,inverse,points[:,1]);heights/=counts
    heights+=seam_offset_mm
    projected=xz[indices];top=np.column_stack([projected[:,0],heights,projected[:,1]])
    spread=max(float(np.ptp(points[inverse==i,1])) for i in range(len(indices)))
    # Duplicate projections use their mean only as a candidate seam. Release
    # checks, not this interpolation, decide whether the proposal is usable.
    triangulation=Delaunay(projected);n=len(top)
    bottom=top.copy();bottom[:,1]=-depth-1
    faces=[]
    # Delaunay triangles are CCW in X,Z; reverse for +Y-facing top.
    for a,b,c in triangulation.simplices:faces.extend([[a,c,b],[a+n,b+n,c+n]])
    # Determine oriented perimeter from top triangles, then close downwards.
    directed={}
    for a,b,c in faces[::2]:
        for u,v in [(a,b),(b,c),(c,a)]:
            key=tuple(sorted([u,v]));directed.setdefault(key,[]).append((u,v))
    for uses in directed.values():
        if len(uses)==1:
            a,b=uses[0];faces.extend([[b,a,a+n],[b,a+n,b+n]])
    below=trimesh.Trimesh(np.vstack([top,bottom]),faces,process=True)
    if not below.is_volume:raise ValueError('Parting field did not form a closed solid')
    total=boolean('union',candidate['plaster'])
    minus=boolean('intersection',[total,below]);plus=boolean('difference',[total,below])
    parts=[]
    for part in [plus,minus]:
        reread=trimesh.load_mesh(io.BytesIO(part.export(file_type='stl')),file_type='stl')
        if not reread.is_volume:raise ValueError('Partition failed STL round-trip validation')
        parts.append(reread)
    return {**candidate,'plaster':parts,'masters':[],'walls':[],
            'seam':{'method':'silhouette_delaunay_heightfield','vertices':len(top),'seam_offset_mm':seam_offset_mm,'max_duplicate_height_spread_mm':spread,'limitation':'Unconstrained triangulation is a proposal; release must be checked. Registration is not preserved.'},'seam_field':below}
