import os
os.environ['PYOPENGL_PLATFORM'] = 'egl'
os.environ['PYGLET_HEADLESS'] = '1'
import trimesh
import pyrender
import numpy as np
import argparse
import cv2
import math

import os
os.environ['PYOPENGL_PLATFORM'] = 'egl'

import trimesh
import pyrender
import numpy as np
import argparse
import cv2
import math

# ==========================================
# 辅助函数：绘制 Header 文字
# ==========================================
def create_header(text, width, height=150):
    """生成带有居中文字的纯白背景 Header"""
    canvas = np.ones((height, width, 3), dtype=np.uint8) * 255
    font = cv2.FONT_HERSHEY_DUPLEX
    font_scale = 2.5
    thickness = 4
    text_color = (60, 60, 60) # 高级深灰色

    text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
    text_x = (width - text_size[0]) // 2
    text_y = (height + text_size[1]) // 2 # 垂直居中

    cv2.putText(canvas, text, (text_x, text_y), font, font_scale, text_color, thickness, cv2.LINE_AA)
    return canvas

# ==========================================
# 辅助函数：智能 Bounding Box 裁剪与统一 (修复 Off-by-one 报错)
# ==========================================
def process_images_with_bbox(img_paths, block_size=800, padding=40):
    """提取透明 PNG 的 Bounding Box，统一最大尺寸，并贴在白底上"""
    raw_images = []
    centers = []
    max_dim = 0

    # 1. 第一遍扫描：分析所有图片的 Alpha 通道，找到统一的最大规格
    for path in img_paths:
        if os.path.exists(path):
            img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
            if img is not None and img.shape[2] == 4:
                raw_images.append(img)
                # 提取透明通道找边界
                alpha = img[:, :, 3]
                # 容错阈值 10 (非全透明)
                y_idx, x_idx = np.where(alpha > 10) 
                
                if len(y_idx) > 0:
                    y_min, y_max = y_idx.min(), y_idx.max()
                    x_min, x_max = x_idx.min(), x_idx.max()
                    h, w = y_max - y_min, x_max - x_min
                    cx, cy = (x_min + x_max) // 2, (y_min + y_max) // 2
                    
                    # 记录 4 张图里最大的一个维度作为基准
                    max_dim = max(max_dim, h, w)
                    centers.append((cx, cy))
                    continue

        # 失败或非透明图片保底
        print(f"Warning: Issue with {path}, using dummy placeholder.")
        dummy = np.zeros((800, 800, 4), dtype=np.uint8)
        raw_images.append(dummy)
        centers.append((400, 400))
        max_dim = max(max_dim, 800)

    # 2. 第二遍：统一尺寸并裁剪
    # 基准规格是最大维度加上 Padding
    target_size = max_dim + padding * 2
    final_imgs = []
    half = target_size // 2

    for img, (cx, cy) in zip(raw_images, centers):
        h_orig, w_orig = img.shape[:2]
        
        # 准备统一规格的透明画布 (H x W x 4)
        unified_canvas = np.zeros((target_size, target_size, 4), dtype=np.uint8)

        # 算出如果物体居中，理想状态下在原图上的坐标范围
        y1_src_orig, y2_src_orig = cy - half, cy + half
        x1_src_orig, x2_src_orig = cx - half, cx + half

        # 【鲁棒性修复重点】：处理边界溢出和奇偶数误差 (Off-by-one)
        # 1. 计算源图像有效的裁剪区域 ( coordinates clamped to image boundary )
        y1_src = max(0, y1_src_orig)
        y2_src = min(h_orig, y2_src_orig)
        x1_src = max(0, x1_src_orig)
        x2_src = min(w_orig, x1_src_orig + (y2_src - y1_src)) # 强行保持方形 W = H

        src_h_final = y2_src - y1_src
        src_w_final = x2_src - x1_src

        if src_h_final <= 0 or src_w_final <= 0: continue

        # 2. 计算在目标统一画布上的起始贴图位置
        # 如果源坐标是负数，表示要从画布的 [0] 位置开始贴
        y1_dst = max(0, -y1_src_orig)
        x1_dst = max(0, -x1_src_orig)

        # 3. 计算在画布上的结束位置
        y2_dst = min(target_size, y1_dst + src_h_final)
        x2_dst = min(target_size, x1_dst + src_w_final)

        # 【核心强校验逻辑】：强行比较 H 和 W
        final_valid_h = y2_dst - y1_dst
        final_valid_w = x2_dst - x1_dst
        
        # 再次反推，强行修正源图像裁剪范围，确保 W:H = final_valid_w:final_valid_h 
        y2_src = y1_src + final_valid_h
        x2_src = x1_src + final_valid_w

        # 提取源图像切片
        src_slice = img[y1_src:y2_src, x1_src:x2_src]

        # 终极保护：如果即使经历了上面所有保护逻辑， NumPy 切片尺寸仍然偏离了±1像素 (几乎不可能发生)
        if (src_slice.shape[0] != final_valid_h) or (src_slice.shape[1] != final_valid_w):
            # 强行用 opencv 将源切片缩放到目标切片格子的尺寸
            # print(f"DEBUG: Off-by-one fixed: {src_slice.shape} resized to ({final_valid_h, final_valid_w})")
            src_slice = cv2.resize(src_slice, (final_valid_w, final_valid_h), interpolation=cv2.INTER_AREA)

        # 4. 执行贴图 (此时 H和W 绝对百分之百能匹配，不会再报错)
        try:
            unified_canvas[y1_dst:y2_dst, x1_dst:x2_dst] = src_slice
        except ValueError as e:
            # 兜底：万一 src_slice 还是有点小误差
            unified_canvas[y1_dst:y2_dst, x1_dst:x2_dst] = cv2.resize(src_slice, (final_valid_w, final_valid_h), interpolation=cv2.INTER_AREA)


        # 3. 将统一规格的图片缩放到田字格的目标格子大小，并融合纯白背景
        resized = cv2.resize(unified_canvas, (block_size, block_size), interpolation=cv2.INTER_AREA)
        white_bg = np.ones((block_size, block_size, 3), dtype=np.uint8) * 255
        
        # 处理带有 Alpha 通道的融合
        alpha_mask = resized[:, :, 3].astype(float) / 255.0
        for c in range(3):
            white_bg[:, :, c] = (resized[:, :, c] * alpha_mask + white_bg[:, :, c] * (1 - alpha_mask)).astype(np.uint8)
            
        final_imgs.append(white_bg)

    return final_imgs

# ==========================================
#辅助函数：3D 渲染相关
# ==========================================
def get_look_at_pose(eye, target, up=[0, 1, 0]):
    eye, target, up = np.array(eye, dtype=float), np.array(target, dtype=float), np.array(up, dtype=float)
    forward = target - eye
    forward /= np.linalg.norm(forward)
    z_axis = -forward
    x_axis = np.cross(up, z_axis)
    x_axis /= np.linalg.norm(x_axis)
    y_axis = np.cross(z_axis, x_axis)
    pose = np.eye(4)
    pose[:3, 0], pose[:3, 1], pose[:3, 2], pose[:3, 3] = x_axis, y_axis, z_axis, eye
    return pose

def render_view(r, mesh, camera, camera_pose):
    scene = pyrender.Scene(bg_color=[1.0, 1.0, 1.0, 1.0])
    scene.add(mesh, pose=np.eye(4))
    scene.add(camera, pose=camera_pose)
    scene.add(pyrender.DirectionalLight(color=np.ones(3), intensity=2.5), pose=camera_pose)
    color, _ = r.render(scene)
    return color

# ==========================================
# 主体生成逻辑
# ==========================================
def create_poster(img_paths, mesh_path, output_path):
    block_size = 800
    header_h = 150

    print("1. Processing Input Images (Smart Bounding Box)...")
    # padding=40 表示在物体的绝对边缘外留 40 像素的防呆边距
    imgs = process_images_with_bbox(img_paths, block_size, padding=40)
    
    # 拼装 2x2 输入田字格
    grid_inputs = np.vstack((np.hstack((imgs[0], imgs[1])), np.hstack((imgs[2], imgs[3]))))
    
    # 拼装左侧模块 (Header + Grid)
    col_inputs = np.vstack((create_header("Sparse Views", 1600, header_h), grid_inputs))

    print("2. Setting up 3D Scene...")
    mesh = trimesh.load(mesh_path, process=False)
    if isinstance(mesh, trimesh.Scene):
        mesh = list(mesh.geometry.values())[0] if len(mesh.geometry) == 1 else trimesh.util.concatenate(tuple(mesh.geometry.values()))
    
    mesh.vertices -= mesh.vertices.mean(axis=0)
    mesh.vertices /= np.max(np.linalg.norm(mesh.vertices, axis=1))
    
    clay_color = np.array([190, 190, 190, 255])
    mesh.visual = trimesh.visual.ColorVisuals(vertex_colors=np.tile(clay_color, (mesh.vertices.shape[0], 1)))
    pyr_mesh = pyrender.Mesh.from_trimesh(mesh)
    r = pyrender.OffscreenRenderer(block_size, block_size)

    print("3. Rendering 4 Views Grid...")
    # 可以通过改小 cam_dist 让模型看起来更大一些
    cam_dist = 2.4
    camera_fov = pyrender.PerspectiveCamera(yfov=np.pi / 3.0)
    
    # 渲染 4 个固定视角 (前, 右, 背, 左)
    mesh_views = [render_view(r, pyr_mesh, camera_fov, get_look_at_pose([cam_dist * math.sin(math.radians(ang)), 0, cam_dist * math.cos(math.radians(ang))], [0, 0, 0])) for ang in [0, 90, 180, 270]]
        
    # 拼装 2x2 Mesh 田字格
    grid_mesh = np.vstack((np.hstack((mesh_views[0], mesh_views[1])), np.hstack((mesh_views[2], mesh_views[3]))))
    
    # 拼装中间模块 (Header + Grid)
    col_mesh = np.vstack((create_header("Reconstructed Mesh", 1600, header_h), grid_mesh))

    print("4. Rendering Zoom-ins...")
    # 头部细节特写机位 (侧脸 -90度)
    zoom_head = render_view(r, pyr_mesh, camera_fov, get_look_at_pose(eye=[-0.6, 0.65, 0.0], target=[0.0, 0.65, 0.0]))
    # 鞋子细节特写机位
    zoom_shoes = render_view(r, pyr_mesh, camera_fov, get_look_at_pose(eye=[0.0, -0.85, 0.6], target=[0.0, -0.85, 0.0]))
    
    # 将两个特写上下垂直排布
    col_zoom_images = np.vstack((zoom_head, zoom_shoes))
    
    # 拼装右侧模块 (Header + 垂直特写图)
    col_zoom = np.vstack((create_header("Detail", 800, header_h), col_zoom_images))

    print("5. Drawing Arrow & Assembling...")
    arrow_width = 200
    # 总高度 = 田字格 1600 + Header 150 = 1750
    total_height = 1600 + header_h 
    arrow_canvas = np.ones((total_height, arrow_width, 3), dtype=np.uint8) * 255
    
    # 在箭头画布中央画箭头
    start_pt = (20, total_height // 2)
    end_pt = (180, total_height // 2)
    cv2.arrowedLine(arrow_canvas, start_pt, end_pt, (120, 120, 120), thickness=16, tipLength=0.25)

    # 终极横向拼接：Left_Sparse + Arrow + Mid_Mesh + Right_Detail
    final_img_rgb = np.hstack((col_inputs, arrow_canvas, col_mesh, col_zoom))
    
    # 将颜色空间转换回 BGR 以便于 OpenCV 保存
    #final_img_bgr = cv2.cvtColor(final_img_rgb, cv2.COLOR_RGB2BGR)
    cv2.imwrite(output_path, final_img_rgb)
    print(f"Success! Poster image with BBox and Headers saved to {output_path}")

if __name__ == "__main__":
    # 输入参数设定
    img_paths = [
        "./static/images/input_1.png",
        "./static/images/input_2.png",
        "./static/images/input_3.png",
        "./static/images/input_4.png"
    ]
    mesh_path = "/scratch/chenxiz/SMVRT/experiments/toy_training/evaluation_256_thuman20/meshing/0227/pred_mesh.obj"
    out_path = "./poster_layout.png"
    
    create_poster(img_paths, mesh_path, out_path)