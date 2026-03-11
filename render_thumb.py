import os
# 【关键】强制使用 EGL 模式，防止在没有显示器的 Linux 服务器上报错
os.environ['PYOPENGL_PLATFORM'] = 'egl'
os.environ['PYGLET_HEADLESS'] = '1'

import trimesh
import pyrender
import numpy as np
import argparse
from PIL import Image

import trimesh
import pyrender
import numpy as np
import argparse
from PIL import Image

def render_thumbnail(mesh_path, out_path, resolution=512):
    print(f"Loading {mesh_path}...")
    mesh = trimesh.load(mesh_path, process=False)
    
    # 【修复重点】：如果读进来的是一个 Scene 场景，提取里面的实际 3D 模型
    if isinstance(mesh, trimesh.Scene):
        if len(mesh.geometry) == 0:
            print("Error: No geometry found in the scene.")
            return
        elif len(mesh.geometry) == 1:
            # 如果场景里只有一个模型，直接取出来
            mesh = list(mesh.geometry.values())[0]
        else:
            # 如果有多个部件，把它们合并成一个完整的模型
            mesh = trimesh.util.concatenate(tuple(mesh.geometry.values()))

    # 【自动对齐与缩放】
    vertices = mesh.vertices - mesh.vertices.mean(axis=0) # 居中
    max_dist = np.max(np.linalg.norm(vertices, axis=1))
    mesh.vertices = vertices / max_dist # 缩放到单位球内
    
    # 颜色处理
    if not hasattr(mesh.visual, 'vertex_colors') or mesh.visual.vertex_colors is None:
        mesh.visual.vertex_colors = np.array([200, 200, 200, 255])
    
    pyr_mesh = pyrender.Mesh.from_trimesh(mesh)
    
    # 设置纯白背景 [R, G, B, Alpha]
    scene = pyrender.Scene(bg_color=[1.0, 1.0, 1.0, 1.0]) 
    scene.add(pyr_mesh)

    # 设置相机
    camera = pyrender.PerspectiveCamera(yfov=np.pi / 3.0)
    camera_pose = np.array([
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 2.5], 
        [0.0, 0.0, 0.0, 1.0]
    ])
    scene.add(camera, pose=camera_pose)

    # 设置光照
    light = pyrender.DirectionalLight(color=np.ones(3), intensity=3.5)
    scene.add(light, pose=camera_pose)

    # 离屏渲染
    print("Rendering...")
    r = pyrender.OffscreenRenderer(resolution, resolution)
    color, depth = r.render(scene)
    
    # 保存为 PNG
    img = Image.fromarray(color)
    img.save(out_path)
    print(f"Success! Saved thumbnail to {out_path}\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Path to input mesh (.ply, .obj, .glb)")
    parser.add_argument("--output", "-o", help="Path to output .png", default="thumb.png")
    args = parser.parse_args()
    
    render_thumbnail(args.input, args.output)