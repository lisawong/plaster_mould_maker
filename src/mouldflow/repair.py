"""Conservative boundary stitching; may leave difficult inputs unrepaired."""
import numpy as np
import trimesh
from scipy.spatial import cKDTree

def stitch_boundaries(mesh,tolerance_mm):
    if tolerance_mm<=0 or not np.isfinite(tolerance_mm):raise ValueError('Positive finite stitch tolerance required')
    mesh=mesh.copy();vertices=mesh.vertices.copy()
    counts=np.bincount(mesh.edges_unique_inverse)
    edges=mesh.edges_unique[counts==1]
    if not len(edges):return mesh
    boundary=np.unique(edges);tree=cKDTree(vertices[boundary]);splits={}
    for a,b in edges:
        delta=vertices[b]-vertices[a];length=np.linalg.norm(delta)
        if length<1e-10:continue
        candidates=boundary[tree.query_ball_point((vertices[a]+vertices[b])/2,length/2+tolerance_mm)]
        t=(vertices[candidates]-vertices[a])@delta/(length*length)
        dist=np.linalg.norm(vertices[candidates]-(vertices[a]+t[:,None]*delta),axis=1)
        valid=(t>1e-5)&(t<1-1e-5)&(dist<=tolerance_mm)
        candidates=candidates[valid];t=t[valid]
        if len(candidates):splits[(int(a),int(b))]=candidates[np.argsort(t)].tolist()
    out_vertices=vertices.tolist();out_faces=[]
    for face in mesh.faces:
        polygon=[]
        for a,b in zip(face,np.roll(face,-1)):
            polygon.append(int(a));key=tuple(sorted((int(a),int(b))))
            inserted=splits.get(key,[])
            if a>b:inserted=inserted[::-1]
            polygon.extend(i for i in inserted if i not in face)
        if len(polygon)==3:out_faces.append(face.tolist())
        else:
            centre=len(out_vertices);out_vertices.append(vertices[face].mean(axis=0).tolist())
            out_faces.extend([centre,a,b] for a,b in zip(polygon,polygon[1:]+polygon[:1]))
    result=trimesh.Trimesh(out_vertices,out_faces,process=True)
    result.update_faces(result.nondegenerate_faces());result.remove_unreferenced_vertices()
    return result


def project_to_reference(repaired,reference,max_distance_mm):
    """Recover the reference surface after topology repair, within an explicit bound.

    This preserves topology, not a guarantee against triangle self-intersection.
    Revalidate the returned mesh before use.
    """
    if not np.isfinite(max_distance_mm) or max_distance_mm<=0:raise ValueError('Positive projection limit required')
    result=repaired.copy();projected=[];distances=[]
    for start in range(0,len(result.vertices),1024):
        closest,distance,_=trimesh.proximity.closest_point(reference,result.vertices[start:start+1024])
        if not np.isfinite(distance).all() or np.any(distance>max_distance_mm):
            raise ValueError('Reference projection exceeds permitted repair distance')
        projected.append(closest);distances.extend(distance.tolist())
    result.vertices=np.concatenate(projected)
    return result,{'max_displacement_mm':max(distances),'mean_displacement_mm':float(np.mean(distances)),
                   'watertight':bool(result.is_watertight),'winding_consistent':bool(result.is_winding_consistent)}
