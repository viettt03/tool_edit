import subprocess

input_audio = "narration.wav"       # Tên file WAV gốc dài 43 phút
output_audio = "output_5p.wav"   # File WAV đầu ra (5 phút đầu)

# Lệnh FFmpeg cắt từ 00:00:00 với thời lượng 5 phút (00:05:00)
command = [
    "ffmpeg",
    "-ss", "00:00:00",      # Thời điểm bắt đầu
    "-t", "00:02:00",       # Độ dài muốn cắt (5 phút)
    "-i", input_audio,
    "-c", "copy",           # Copy luồng dữ liệu, không re-encode (cực nhanh)
    "-y",                   # Ghi đè nếu file đã tồn tại
    output_audio
]

try:
    subprocess.run(command, check=True)
    print(f"Đã cắt thành công! File lưu tại: {output_audio}")
except subprocess.CalledProcessError as e:
    print(f"Lỗi khi xử lý FFmpeg: {e}")
