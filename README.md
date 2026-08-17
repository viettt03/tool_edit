# Cliproom · Vietnamese Video Editor

This CLI creates a Vietnamese narrated video from short clips, optional background music, and styled ASS subtitles. The final video is rendered in one FFmpeg pass, so it does not create and re-encode an intermediate `video.mp4`.

## Setup

1. Install FFmpeg and make sure `ffmpeg` and `ffprobe` are on `PATH`.
2. From `video_editor`, install Python packages:

   ```powershell
   pip install -r requirements.txt
   ```

3. Put files in `input/` and edit `src/config.py`.
4. Run from `video_editor`:

   ```powershell
   python -m src.main
   ```

   For a vertical TikTok render, run:

   ```powershell
   python -m src.main_tiktok
   ```

## Quality and speed

- The default `libx264`, `crf=22`, and `preset="veryfast"` is a good CPU quality/speed balance.
- For faster subtitle generation on CPU, change `whisper_model` from `"small"` to `"base"`. Keep `small` when subtitle accuracy matters more.
- If an NVIDIA GPU and compatible CTranslate2/CUDA setup are available, set `whisper_device="cuda"`, `whisper_compute_type="float16"`, and `video_codec="h264_nvenc"`. The renderer automatically uses NVENC quality options instead of x264 CRF options.
- Set `audio_speed` above `1.0` only when you want a faster voice. At `1.0`, the source audio is reused without creating a WAV intermediate.

## Output

- Final video: `output/final.mp4`
- Styled subtitles: `output/subtitles.ass`
- TikTok video: `output/tiktok_final.mp4`
- TikTok subtitles: `output/tiktok_subtitles.ass`
Project này có hai phần:

1. **Cliproom GUI**: dán link Douyin, link profile hoặc từ khóa để tải video.
2. **Video Editor CLI**: lấy audio tiếng Việt + các video ngắn trong `input/videos/` để dựng video cuối.

## Yêu cầu

- macOS
- Python 3.10 trở lên
- FFmpeg và FFprobe đã có trong PATH
- Google Chrome, nếu muốn dùng cookie phiên Douyin hiện tại

Kiểm tra nhanh:

```bash
python3 --version
ffmpeg -version
ffprobe -version
```

## Cài đặt lần đầu

Mở Terminal và chạy:

```bash
cd /Users/ducytcg123456/Desktop/tool/tool_edit/video_editor

python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
```

Nếu thư mục `.venv` đã tồn tại thì không cần chạy lại lệnh tạo môi trường ảo.

## Cách chạy giao diện GUI

Chạy lệnh sau từ thư mục `video_editor`:

```bash
cd /Users/ducytcg123456/Desktop/tool/tool_edit/video_editor
./.venv/bin/python -m src.desktop_app
```

Lệnh này sẽ:

- Khởi động server local.
- Mở Cliproom trong một cửa sổ Chrome riêng.
- Cho phép dán nhiều link video, mỗi dòng một link.
- Cho phép chọn `Một video`, `User` hoặc `Từ khóa`.
- Dùng Chrome đã render JavaScript để đọc kết quả `User` và `Từ khóa`.
- Tải song song tối đa 3 video.
- Lưu video vào `input/videos/`.

Nếu cửa sổ không tự mở, mở trình duyệt vào:

```text
http://127.0.0.1:8765
```

Để dừng app, quay lại Terminal và nhấn `Ctrl + C`.

### Tự động upload TikTok, dừng trước nút Post

Cliproom có chế độ tự động bằng Playwright:

1. Trong phần `TikTok upload`, bấm `Mở Chrome và tự upload` một lần.
2. Đăng nhập Gmail/TikTok và xử lý 2FA/CAPTCHA thủ công trên Chrome thường vừa mở.
3. Cliproom tự lấy `output/final.mp4`, tự điền caption mặc định, upload và dừng trước nút `Post`.
4. Kiểm tra lại trên Chrome và tự bấm `Post`.

Caption mặc định là `Một câu chuyện ngắn đáng nghe đến cuối. #kechuyen #truyenngan`.
Muốn đổi caption, tạo file `output/tiktok_caption.txt`; Cliproom sẽ tự đọc nội dung
file này (tối đa 2.200 ký tự) ở lượt upload tiếp theo.

Chrome dùng profile riêng tại `video_editor/.playwright/tiktok-profile` và cổng kết nối
local `9222`. Playwright chỉ kết nối vào Chrome sau khi Chrome đã mở, không tự động
đăng nhập Gmail, xử lý CAPTCHA, mã 2FA hoặc bấm `Post`. Nếu TikTok yêu cầu xác minh,
hãy hoàn tất thủ công rồi Cliproom sẽ tự tiếp tục.

Video được chọn từ `output/final.mp4`. Cửa sổ Chrome phải còn mở trong suốt quá
trình Cliproom chuẩn bị upload.

### Dùng giao diện để tải video

#### Một video

Dán một trong các link sau vào ô nhập:

```text
https://www.douyin.com/video/7645302877548997029
https://www.douyin.com/jingxuan?modal_id=7645302877548997029
```

#### Nhiều video

Dán mỗi link một dòng:

```text
https://www.douyin.com/video/1111111111111111111
https://www.douyin.com/video/2222222222222222222
https://www.douyin.com/video/3333333333333333333
```

#### Video từ profile

Chọn tab `User`, dán link profile, chọn số video tối đa rồi tải. App sẽ cố lấy danh sách video mới nhất trước.

#### Video từ từ khóa

Chọn tab `Từ khóa`, nhập từ khóa tiếng Trung hoặc tiếng Việt, chọn số lượng rồi tải. App sẽ cố sắp xếp kết quả theo ngày đăng mới nhất trước.

## Cookie Douyin

Nếu Douyin hiện yêu cầu đăng nhập hoặc CAPTCHA:

1. Mở Douyin bằng Chrome.
2. Đăng nhập hoặc hoàn tất xác minh kéo thả thủ công.
3. Giữ Chrome ở đúng profile đang đăng nhập.
4. Chọn `Chrome hiện tại` trong giao diện Cliproom.
5. Chạy lại lượt tải.

Với chế độ `Từ khóa` hoặc `User`, Cliproom sẽ mở một cửa sổ Chrome riêng để
render trang Douyin. Nếu có CAPTCHA, trạng thái sẽ chuyển sang `Đang chờ xác
minh`; kéo CAPTCHA thủ công trên cửa sổ đó, trang sẽ được đọc lại tự động. Nếu
đã hết thời gian chờ, quay lại Cliproom và bấm `Tải video xuống` lại. Không cần
nhập API CAPTCHA hoặc gửi ảnh/cookie ra dịch vụ bên ngoài.

Không gửi file cookie, mã QR, mật khẩu hoặc nội dung cookie cho người khác.

## Chạy bằng CLI, không dùng giao diện

### Một video

```bash
cd /Users/ducytcg123456/Desktop/tool/tool_edit/video_editor
./.venv/bin/python -m src.douyin \
  --video-url "https://www.douyin.com/video/7645302877548997029"
```

### Một profile

```bash
./.venv/bin/python -m src.douyin \
  --user-url "https://www.douyin.com/user/..." \
  --limit 20
```

### Tìm theo từ khóa

```bash
./.venv/bin/python -m src.douyin \
  --keyword "truyện ngắn" \
  --limit 20
```

## Chạy pipeline dựng video

Chuẩn bị các file:

```text
input/narration.mp3    # audio tiếng Việt
input/music.mp3        # nhạc nền, có thể bỏ qua nếu không dùng
input/videos/*.mp4     # video ngắn đã tải
```

Sau đó chạy:

```bash
cd /Users/ducytcg123456/Desktop/tool/tool_edit/video_editor
./.venv/bin/python -m src.main
```

Video cuối sẽ nằm tại:

```text
output/final.mp4
```

Phụ đề tự động sẽ nằm tại:

```text
output/subtitles.srt
```

Lần đầu chạy, `faster-whisper` có thể tải model Whisper về máy. Thời gian chạy phụ thuộc độ dài audio và model được chọn trong `src/main.py`.

## Tự động dịch truyện → Vbee → video kể chuyện

Pipeline mới dùng một transcript đã copy từ Douyin, dịch sang tiếng Việt, gọi
Vbee tạo audio, tạo phụ đề bằng Whisper rồi ghép với một video Douyin từ đầu.
Video đầu ra mặc định là 1920x1080 theo kiểu video mẫu: video chính ở giữa,
nền mờ hai bên, logo góc trên, waveform giữa khung hình và phụ đề phía dưới.

Vbee không phải bộ dịch; Vbee chỉ chuyển văn bản thành giọng nói. Pipeline dùng
bộ dịch online cho bước tiếng Trung → tiếng Việt. Khi cần giữ quyền kiểm soát
nội dung dịch, có thể sửa file `output/story_vi.txt` sau bước dịch rồi chạy
riêng phần TTS ở phiên bản tiếp theo.

### Cấu hình Vbee

Tạo App ID và Token trên `https://api.vbee.vn/`, sau đó thiết lập biến môi
trường trong Terminal. Không ghi token trực tiếp vào source code:

```bash
cd /Users/ducytcg123456/Desktop/tool/tool_edit/video_editor
export VBEE_APP_ID="app-id-cua-ban"
export VBEE_TOKEN="token-cua-ban"
export VBEE_VOICE_CODE="hn_female_ngochuyen_full_48k-fhg"
```

Bạn có thể chọn mã giọng khác từ danh sách voice của Vbee. API xử lý bất đồng
bộ, vì vậy pipeline tự chờ request hoàn tất rồi tải `audio_link` về máy.

### Chạy pipeline

1. Copy transcript tiếng Trung vào file `input/story_zh.txt`.
2. Đặt logo PNG nền trong suốt tại `input/logo.png`.
3. Đặt video Douyin muốn dùng tại `input/videos/` hoặc truyền chính xác bằng
   `--video`.
4. Cài thêm bộ dịch và chạy:

```bash
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python -m src.story_pipeline \
  --source-text input/story_zh.txt \
  --video input/videos/7645302877548997029.mp4 \
  --logo input/logo.png
```

Kết quả nằm ở:

```text
output/story_vi.txt
output/narration_vbee.mp3
output/story_subtitles.srt
output/story_final.mp4
```

Nếu file nguồn đã là tiếng Việt, bỏ qua bộ dịch:

```bash
./.venv/bin/python -m src.story_pipeline \
  --source-text input/story_vi.txt \
  --no-translate \
  --video input/videos/7645302877548997029.mp4
```

Nếu chưa có transcript nhưng video Douyin có lời thoại tiếng Trung, có thể để
Whisper nhận diện audio trước rồi dịch:

```bash
./.venv/bin/python -m src.story_pipeline \
  --source-video input/videos/7645302877548997029.mp4 \
  --source-language zh \
  --video input/videos/7645302877548997029.mp4
```

Lệnh trên chưa đọc chữ nằm trên màn hình video (OCR); nó nhận diện lời thoại
trong audio. Với truyện đã có bản chép lời, dùng `--source-text` sẽ chính xác
hơn.

## Một số cấu hình chính

Mở `src/main.py` để chỉnh:

```python
video_format="vertical"       # video dọc 1080x1920
video_format="horizontal"     # video ngang 1920x1080
audio_speed=1.0                # tốc độ audio
music_volume=0.12              # âm lượng nhạc nền
whisper_model="small"          # model nhận diện tiếng Việt
```

## Nếu báo lỗi port 8765 đang được sử dụng

Dừng app cũ bằng `Ctrl + C`, hoặc kiểm tra process:

```bash
lsof -i :8765
```

Sau đó chạy lại:

```bash
./.venv/bin/python -m src.desktop_app
```
