import os
os.environ['PYOPENGL_PLATFORM'] = 'egl'
os.environ['PYGLET_HEADLESS'] = '1'
import trimesh
import pyrender
import numpy as np
import argparse
from PIL import Image
import math
import cv2 # 用于最后把图片直接合成视频
import imageio

def render_turntable(mesh_path, output_dir, frames=120, resolution=800, elevation_deg=0):
    print(f"Loading {mesh_path}...")
    mesh = trimesh.load(mesh_path, process=False)
    
    if isinstance(mesh, trimesh.Scene):
        if len(mesh.geometry) == 0:
            print("Error: No geometry found in the scene.")
            return
        elif len(mesh.geometry) == 1:
            mesh = list(mesh.geometry.values())[0]
        else:
            mesh = trimesh.util.concatenate(tuple(mesh.geometry.values()))

    # 居中和归一化
# 设置一个高级、柔和的白模材质颜色 (比如石膏灰)
    clay_color = np.array([190, 190, 190, 255])
    
    if isinstance(mesh, trimesh.Scene):
        if len(mesh.geometry) == 0: print("Error"); return
        mesh = list(mesh.geometry.values())[0] if len(mesh.geometry) == 1 else trimesh.util.concatenate(tuple(mesh.geometry.values()))

    # 居中和归一化 (核心步骤)
    vertices = mesh.vertices - mesh.vertices.mean(axis=0)
    max_dist = np.max(np.linalg.norm(vertices, axis=1))
    mesh.vertices = vertices / max_dist
    
    # 【修复重点】：既然是纯几何展示，我们强制移除可能存在的糟糕颜色，统一赋予石膏灰材质
    mesh.visual = trimesh.visual.ColorVisuals(vertex_colors=np.tile(clay_color, (mesh.vertices.shape[0], 1)))
    
    pyr_mesh = pyrender.Mesh.from_trimesh(mesh)
    scene = pyrender.Scene(bg_color=[1.0, 1.0, 1.0, 1.0]) # 纯白背景
    mesh_node = scene.add(pyr_mesh, pose=np.eye(4))

    # ==========================================
    # 核心升级：电影级摇臂相机 (Crane Shot) 设置
    # ==========================================
# ==========================================
    # 核心控制变量
    # ==========================================
    camera = pyrender.PerspectiveCamera(yfov=np.pi / 3.0)
    light_top = pyrender.DirectionalLight(color=np.ones(3), intensity=2.5)
    light_bottom = pyrender.DirectionalLight(color=np.ones(3), intensity=1.5)
    
    # 1. 相机距离 (原本是 2.5，如果觉得人太大可以改成 2.6 或 2.7)
    cam_dist = 2.65 
    
    # 2. 【修改这里】摇臂的最大仰/俯角度。
    # 之前是 20，现在改成 10，保证人物头脚绝对不会飞出屏幕！
    crane_amplitude_deg = 2.5 

    r = pyrender.OffscreenRenderer(resolution, resolution)
    os.makedirs(output_dir, exist_ok=True)
    
    frames_phase1 = 120 # 阶段1：原地平转一圈 (4秒)
    frames_phase2 = 120 # 阶段2：摇臂再转一圈 (4秒)
    
    video_writer = imageio.get_writer(
            f"{output_dir}/227.mp4", 
            fps=30, 
            codec='libx264', 
            pixelformat='yuv420p'  # 这是网页端能顺利播放的终极魔法参数
        )
    # ==========================================
    # 阶段 1：原地纯水平环视一圈
    # ==========================================
    print("Phase 1: Flat 360 degree rotation...")
    for i in range(frames_phase1):
        # 模特自转
        theta = 2.0 * math.pi * i / frames_phase1
        rot_y = np.array([
            [math.cos(theta), 0, math.sin(theta), 0],
            [0, 1, 0, 0],
            [-math.sin(theta), 0, math.cos(theta), 0],
            [0, 0, 0, 1]
        ])
        scene.set_pose(mesh_node, rot_y)
        
        # 相机固定平视 (俯仰角 = 0)
        camera_pose = np.array([
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, cam_dist],
            [0.0, 0.0, 0.0, 1.0]
        ])
        
        for node in scene.get_nodes():
            if node.camera or node.light: scene.remove_node(node)
            
        scene.add(camera, pose=camera_pose)
        scene.add(light_top, pose=camera_pose) 

        color, _ = r.render(scene)
        video_writer.append_data(color)

    # ==========================================
    # 阶段 2：带有摇臂效果的第二圈
    # ==========================================
    print("Phase 2: Crane shot rotation...")
    for i in range(frames_phase2):
        # 模特继续顺滑自转
        theta = 2.0 * math.pi * i / frames_phase2
        rot_y = np.array([
            [math.cos(theta), 0, math.sin(theta), 0],
            [0, 1, 0, 0],
            [-math.sin(theta), 0, math.cos(theta), 0],
            [0, 0, 0, 1]
        ])
        scene.set_pose(mesh_node, rot_y)
        
        # 相机俯仰角使用正弦波平滑过渡
        phase = 2.0 * math.pi * i / frames_phase2
        curr_elev_deg = crane_amplitude_deg * math.sin(phase)
        curr_elev_rad = math.radians(curr_elev_deg)
        
        cam_y = cam_dist * math.sin(curr_elev_rad)
        cam_z = cam_dist * math.cos(curr_elev_rad)
        
        camera_pose = np.array([
            [1.0, 0.0, 0.0, 0.0],
            [0.0, math.cos(curr_elev_rad), -math.sin(curr_elev_rad), cam_y],
            [0.0, math.sin(curr_elev_rad), math.cos(curr_elev_rad), cam_z],
            [0.0, 0.0, 0.0, 1.0]
        ])
        
        for node in scene.get_nodes():
            if node.camera or node.light: scene.remove_node(node)
            
        scene.add(camera, pose=camera_pose)
        scene.add(light_top, pose=camera_pose) 

        color, _ = r.render(scene)
        video_writer.append_data(color)

    video_writer.close()
    print(f"Done! Saved turntable_final.mp4 in {output_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default='/scratch/chenxiz/SMVRT/experiments/toy_training/evaluation_256_thuman20/meshing/0227/pred_mesh.obj', help="input mesh")#232，317
    parser.add_argument("--outdir", "-o", help="Output directory", default="static/videos")
    parser.add_argument("--elev", type=float, default=15.0, help="Camera elevation angle in degrees (e.g. 15 for slightly top-down)")
    args = parser.parse_args()
    
    render_turntable(args.input, args.outdir, elevation_deg=args.elev)