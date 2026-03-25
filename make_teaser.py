import cv2
import numpy as np
import imageio
import os

def create_sequential_teaser_v2(video_path, img_paths, output_path):
    print(f"Loading video: {video_path}")
    
    # 1. 提取 3D 模型视频的所有帧到内存中
    reader = imageio.get_reader(video_path)
    meta = reader.get_meta_data()
    fps = meta['fps']
    
    video_frames = []
    for frame in reader:
        video_frames.append(frame)
    reader.close()
    
    if not video_frames:
        print("Error: Video is empty.")
        return

    # 视频的高和宽 (假设是 800x800)
    h, w, _ = video_frames[0].shape

    # ==========================================
    # 2. 【升级重点】：处理输入图片 (缩小 + 居中 + 加文字)
    # ==========================================
    imgs_on_white = []
    scale_factor = 0.8 # 【修改点】：缩小到原来的 0.8 倍
    
    # 计算缩小后的尺寸
    scaled_w = int(w * scale_factor)
    scaled_h = int(h * scale_factor)
    # 计算居中所需的偏移量
    x_offset = (w - scaled_w) // 2
    y_offset = (h - scaled_h) // 2

    for p in img_paths:
        # 每帧都先准备一个 800x800 的纯白画布
        final_panel = np.ones((h, w, 3), dtype=np.uint8) * 255
        
        if not os.path.exists(p):
            print(f"Warning: Cannot find {p}.")
            # 如果找不到图片，就留白
        else:
            # 读取带有透明通道的 PNG
            img_bgra = cv2.imread(p, cv2.IMREAD_UNCHANGED)
            if img_bgra is not None:
                
                # 【细节修改】：保持原图比例缩放，不强行拉伸成正方形，避免畸形
                # 找出原图的长边，根据长边来计算缩放比例
                orig_h, orig_w = img_bgra.shape[:2]
                aspect_ratio = orig_w / orig_h
                
                if aspect_ratio > 1:
                    # 宽图，以宽为准
                    fit_w = scaled_w
                    fit_h = int(scaled_w / aspect_ratio)
                else:
                    # 窄图/正方形图，以高为准
                    fit_h = scaled_h
                    fit_w = int(scaled_h * aspect_ratio)
                    
                img_resized = cv2.resize(img_bgra, (fit_w, fit_h))
                
                # 计算再次居中的偏移量 (在 640x640 区域内居中)
                inner_x_offset = x_offset + (scaled_w - fit_w) // 2
                inner_y_offset = y_offset + (scaled_h - fit_h) // 2

                # 执行 Alpha 混合 (处理透明背景)
                if img_resized.shape[2] == 4:
                    b, g, r, a = cv2.split(img_resized)
                    alpha_mask = a.astype(float) / 255.0
                    
                    # 提取画布上对应的区域作为背景
                    roi = final_panel[inner_y_offset:inner_y_offset+fit_h, inner_x_offset:inner_x_offset+fit_w]
                    
                    img_rgb = cv2.merge([r, g, b]).astype(float)
                    # 混合
                    composited = img_rgb * alpha_mask[:,:,np.newaxis] + roi.astype(float) * (1.0 - alpha_mask[:,:,np.newaxis])
                    # 贴回画布
                    final_panel[inner_y_offset:inner_y_offset+fit_h, inner_x_offset:inner_x_offset+fit_w] = composited.astype(np.uint8)
                else:
                    # 没有透明通道，直接贴
                    img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)
                    final_panel[inner_y_offset:inner_y_offset+fit_h, inner_x_offset:inner_x_offset+fit_w] = img_rgb
            else:
                 print(f"Error reading {p}")

        # ==========================================
        # 【升级重点 2】：在图片上方绘制 "4 views" 文字
        # ==========================================
        text = "4 views"
        # 使用 OpenCV 内置的字体
        font = cv2.FONT_HERSHEY_DUPLEX
        font_scale = 1.2    # 字体大小
        font_thickness = 2  # 字体粗细
        text_color = (80, 80, 80) # RGB：深灰色，不那么刺眼
        
        # 获取文字的宽高，用于居中
        text_size = cv2.getTextSize(text, font, font_scale, font_thickness)[0]
        text_x = (w - text_size[0]) // 2  # 水平居中
        # 垂直位置：距离顶部 8% 的高度
        text_y = int(h * 0.08) + text_size[1]
        
        # 将文字绘制到画布上 (注意：final_panel 此时是 RGB 格式，putText 接受 RGB)
        cv2.putText(final_panel, text, (text_x, text_y), font, font_scale, text_color, font_thickness, cv2.LINE_AA)
        
        imgs_on_white.append(final_panel)

    # 3. 准备静态元素的画布
    arrow_width = int(w * 0.3)
    white_mid = np.ones((h, arrow_width, 3), dtype=np.uint8) * 255
    arrow_canvas = white_mid.copy()
    start_pt = (int(arrow_width * 0.1), h // 2)
    end_pt = (int(arrow_width * 0.9), h // 2)
    # 保持上次的加粗箭头
    cv2.arrowedLine(arrow_canvas, start_pt, end_pt, (120, 120, 120), thickness=12, tipLength=0.25)

    white_right = np.ones((h, w, 3), dtype=np.uint8) * 255

    # 4. 定义时间轴
    phase1_frames = len(imgs_on_white) * int(fps) 
    phase2_frames = int(fps * 0.5)
    phase3_frames = len(video_frames)
    total_frames = phase1_frames + phase2_frames + phase3_frames

    print(f"Writing sequential teaser v2 to: {output_path}")
    writer = imageio.get_writer(
        output_path, 
        format='FFMPEG', 
        fps=fps, 
        codec='libx264', 
        pixelformat='yuv420p'
    )

    # 5. 根据时间轴逐帧合成
    for i in range(total_frames):
        # --- 左侧逻辑 ---
        if i < phase1_frames:
            img_idx = i // int(fps)
            left_panel = imgs_on_white[img_idx]
        else:
            left_panel = imgs_on_white[-1]
            
        # --- 中间逻辑 ---
        if i < phase1_frames:
            mid_panel = white_mid
        else:
            mid_panel = arrow_canvas
            
        # --- 右侧逻辑 ---
        if i < phase1_frames + phase2_frames:
            right_panel = white_right
        else:
            vid_idx = i - (phase1_frames + phase2_frames)
            right_panel = video_frames[vid_idx]

        combined_frame = np.hstack((left_panel, mid_panel, right_panel))
        writer.append_data(combined_frame)
        
        if i % 30 == 0:
            print(f"Processed {i}/{total_frames} frames")

    writer.close()
    print("Success! Your cinematic teaser v2 is ready.")

if __name__ == "__main__":
    video_in = "./static/videos/227.mp4"
    images_in = [
        "./static/images/input_1.png",
        "./static/images/input_2.png",
        "./static/images/input_3.png",
        "./static/images/input_4.png"
    ]
    # 修改输出文件名，避免混淆
    video_out = "./static/videos/teaser_v2.mp4"
    
    create_sequential_teaser_v2(video_in, images_in, video_out)