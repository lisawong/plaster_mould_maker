"""Detect strict edge-through-face crossings missed by watertightness checks."""
import numpy as np

def find_edge_face_crossings(mesh,tolerance_mm=1e-6,batch_size=512):
    if not np.isfinite(tolerance_mm) or tolerance_mm<=0:raise ValueError('Positive finite tolerance required')
    edges=mesh.edges_unique;origins=mesh.vertices[edges[:,0]];delta=mesh.vertices[edges[:,1]]-origins
    lengths=np.linalg.norm(delta,axis=1);directions=delta/np.maximum(lengths[:,None],1e-30)
    findings=[]
    for start in range(0,len(edges),batch_size):
        loc,rays,faces=mesh.ray.intersects_location(origins[start:start+batch_size],directions[start:start+batch_size],multiple_hits=True)
        if not len(loc):continue
        ids=rays+start;distance=np.einsum('ij,ij->i',loc-origins[ids],directions[ids])
        strict=(distance>tolerance_mm)&(distance<lengths[ids]-tolerance_mm)
        shared=np.any(mesh.faces[faces]==edges[ids,0,None],axis=1)|np.any(mesh.faces[faces]==edges[ids,1,None],axis=1)
        for p,e,f in zip(loc[strict&~shared],ids[strict&~shared],faces[strict&~shared]):findings.append({'edge_index':int(e),'face_index':int(f),'position_mm':p.tolist()})
    return {'crossing_count':len(findings),'crossings':findings,'tolerance_mm':tolerance_mm,'limitation':'Strict edge-face crossings only; coplanar overlaps and endpoint contacts may be missed. Zero is not a complete self-intersection proof.'}
