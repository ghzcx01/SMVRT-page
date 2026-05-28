import qrcode

# 1. 填入你的 Project Page 网址 (必须带 http:// 或 https://)
url = "https://ghzcx01.github.io/gbg-slam-page/"

# 2. 设置二维码参数 (这里设置了极高的容错率和清晰度)
qr = qrcode.QRCode(
    version=1,
    error_correction=qrcode.constants.ERROR_CORRECT_H, # H级容错，哪怕遮挡30%也能扫出
    box_size=20, # 这个值越大，生成的图片分辨率越高
    border=4,    # 四周留白的格子数
)

qr.add_data(url)
qr.make(fit=True)

# 3. 生成黑白二维码并保存
img = qr.make_image(fill_color="black", back_color="white")
img.save("poster_qrcode1.png")
print("Success! 二维码已生成为 poster_qrcode.png")