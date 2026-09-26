"""Render review evidence directly from the generated mesh."""
from pathlib import Path
import os
import numpy as np

def render_input(mesh,path):
    path=Path(path)
    os.environ.setdefault('MPLCONFIGDIR',str(path.parent/'.plot-cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    fig=plt.figure(figsize=(12,6),facecolor='#101b2a')
    fig.text(.04,.94,'INPUT REVIEW',color='white',fontsize=20,weight='bold')
    fig.text(.04,.89,'Dimensions: '+ ' × '.join(f'{x:.2f}' for x in mesh.extents)+' mm  |  review before mould design',color='#c2d5df',fontsize=11)
    radius=max(mesh.extents)*.6;centre=mesh.bounds.mean(axis=0)
    for i,angle in enumerate([-65,35]):
        ax=fig.add_subplot(1,2,i+1,projection='3d',facecolor='#101b2a')
        ax.add_collection3d(Poly3DCollection(mesh.triangles,facecolors='#c99762',shade=True,
                           lightsource=matplotlib.colors.LightSource(azdeg=315,altdeg=45)))
        ax.set(xlim=(centre[0]-radius,centre[0]+radius),ylim=(centre[1]-radius,centre[1]+radius),zlim=(centre[2]-radius,centre[2]+radius))
        ax.set_box_aspect((1,1,1));ax.view_init(elev=25,azim=angle);ax.set_axis_off()
    fig.subplots_adjust(top=.87,bottom=.02,left=.01,right=.99,wspace=0)
    fig.savefig(path,dpi=140,facecolor=fig.get_facecolor());plt.close(fig)
