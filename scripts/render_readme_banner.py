"""Rebuild the README banner with Blender in background mode."""
from pathlib import Path
import bpy, random, math
from mathutils import Vector
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
random.seed(18)
def mat(name, color):
    m=bpy.data.materials.new(name)
    m.diffuse_color=(*color,1)
    m.use_nodes=True
    shader=m.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value=(*color,1)
    shader.inputs['Roughness'].default_value=.85
    return m
green=mat('Pine',(.025,.065,.04))
ivory=mat('Ivory',(.9,.8,.6))
leather=mat('Leather',(.28,.08,.025))
colors=[mat('Rust',(.5,.12,.02)),mat('Ochre',(.65,.3,.04))]
def box(loc,scale,m):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc)
    o=bpy.context.object; o.scale=scale; o.data.materials.append(m)
box((0,0,-.15),(28,14,.2),green)
for x in (4,9): box((x,0,-.035),(.035,14,.015),ivory)
for y in range(-6,7): box((7,y,-.02),(.24,.035,.015),ivory)
bpy.ops.mesh.primitive_uv_sphere_add(segments=64,ring_count=32,location=(6,0,.85))
o=bpy.context.object; o.name='Football'; o.scale=(1.65,.85,.85); o.data.materials.append(leather)
for p in o.data.polygons: p.use_smooth=True
box((6,0,1.71),(1.2,.045,.035),ivory)
for i in range(8): box((5.48+i*.15,0,1.72),(.045,.28,.035),ivory)
for i in range(65):
    x,y=random.uniform(-10,10),random.uniform(-4,4)
    if x<3 and abs(y)<2.5: continue
    bpy.ops.mesh.primitive_circle_add(vertices=5,radius=random.uniform(.1,.23),fill_type='NGON',location=(x,y,.02))
    o=bpy.context.object; o.scale.y=1.6; o.rotation_euler.z=random.uniform(0,6.28); o.data.materials.append(random.choice(colors))
def label(text,loc,size):
    c=bpy.data.curves.new(text,'FONT'); c.body=text; c.size=size
    c.font=bpy.data.fonts.load('/System/Library/Fonts/Supplemental/Georgia.ttf')
    o=bpy.data.objects.new(text,c); bpy.context.collection.objects.link(o); o.location=loc; c.materials.append(ivory)
label('The Revenge',(-8.7,.4,.02),1.65)
label('Game',(-8.7,-1.5,.02),1.65)
bpy.ops.object.light_add(type='AREA',location=(-3,-1,10))
bpy.context.object.data.energy=1800; bpy.context.object.data.size=8; bpy.context.object.data.color=(1,.79,.55)
bpy.ops.object.camera_add(location=(0,-5,20))
c=bpy.context.object; c.rotation_euler=(Vector((0,0,0))-c.location).to_track_quat('-Z','Y').to_euler(); c.data.type='ORTHO'; c.data.ortho_scale=21
s=bpy.context.scene; s.camera=c; s.render.engine='CYCLES'; s.cycles.samples=24; s.cycles.use_denoising=True; s.world.color=(.2,.2,.2)
s.render.resolution_x=1680; s.render.resolution_y=560; s.render.resolution_percentage=100
s.render.filepath=str(Path(__file__).resolve().parents[1]/'docs/screenshots/readme-banner.png')
bpy.ops.render.render(write_still=True)
