import trimesh
import argparse
import os

def convert_to_glb(input_path, output_path=None):
    if not os.path.exists(input_path):
        print(f"Error: File {input_path} not found.")
        return

    if output_path is None:
        # 如果没提供输出路径，默认在同目录下生成同名 .glb
        base_name = os.path.splitext(input_path)[0]
        output_path = f"{base_name}.glb"

    print(f"Loading {input_path}...")
    # process=False 防止 trimesh 自动合并顶点导致 UV 或材质错乱
    mesh = trimesh.load(input_path, process=False)

    # 检查是否成功加载为单个 Mesh 或 Scene
    if isinstance(mesh, trimesh.Scene):
        # 如果是复杂场景（比如带多个部件的 obj），直接导出
        print("Exporting Scene to GLB...")
        mesh.export(output_path)
    else:
        # 如果是单个 Mesh，放入 Scene 中再导出以确保兼容性
        print("Exporting Mesh to GLB...")
        scene = trimesh.Scene(mesh)
        scene.export(output_path)

    print(f"Success! Saved to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert 3D meshes to GLB for web viewing.")
    parser.add_argument("input", help="Path to the input mesh (.ply, .obj, etc.)")
    parser.add_argument("--output", "-o", help="Path to the output .glb file", default=None)
    
    args = parser.parse_args()
    convert_to_glb(args.input, args.output)