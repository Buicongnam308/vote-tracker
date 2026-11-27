# Theo dõi vote Bùi Công Nam (chạy online, 5 phút/lần)

GitHub tự chạy script mỗi 5 phút, lưu số vote kèm mốc thời gian, rồi cập nhật trang web.
Bạn chỉ cần cài đặt một lần, sau đó không cần bật máy.

## Cài đặt (làm một lần, khoảng 10 phút)

1. Đăng ký tài khoản miễn phí tại https://github.com/signup
2. Tạo repo: bấm dấu **+** góc phải trên, chọn **New repository**.
   - Repository name: `vote-tracker`
   - Chọn **Public** (bắt buộc để Actions và Pages miễn phí)
   - Bấm **Create repository**
3. Tải file lên: trong repo mới, bấm **uploading an existing file**.
   - Giải nén file zip, mở thư mục `vote_tracker_online`, chọn **tất cả** bên trong
     (kể cả thư mục `.github`, `docs`, và các file `collect.py`, `config.json`, `README.md`) rồi kéo thả vào trang.
   - Nếu không thấy thư mục `.github` (do Windows ẩn), vào tab View của File Explorer, tick **Hidden items**.
   - Bấm **Commit changes**.
4. Bật Pages: **Settings → Pages → Build and deployment → Source: GitHub Actions**.
5. Chạy lần đầu: tab **Actions** → chọn **track-votes** ở cột trái → **Run workflow** → **Run workflow**.
   Nếu GitHub hỏi "I understand my workflows, go ahead and enable them", bấm đồng ý.
6. Chờ khoảng 2–3 phút. Trang web nằm ở `https://<tên-tài-khoản>.github.io/vote-tracker/`.
   Từ đó GitHub tự chạy mỗi 5 phút (đôi khi trễ vài phút vào giờ cao điểm).

## Thêm bảng Song Write

Trong repo bấm file `config.json`, bấm biểu tượng cây bút (Edit), thay `DAN_LINK_SONG_WRITE_VAO_DAY`
bằng link bảng Song Write, điền `deadline` nếu có (dạng `2026-11-30T23:59:00+07:00`), rồi **Commit changes**.

## Nếu có vấn đề

- Tab **Actions** có dấu X đỏ: bấm vào lần chạy đó, mở bước "Lay so vote va dung trang web",
  chép toàn bộ chữ trong bước đó gửi cho Claude.
- Trang báo "Lần đo gần nhất lỗi": script mở được trang nhưng chưa thấy tên Bùi Công Nam trong dữ liệu.
- Lỗi ở bước "Luu lich su vao repo" (không push được): vào **Settings → Actions → General →
  Workflow permissions**, chọn **Read and write permissions**, bấm Save, rồi chạy lại.
- Số hiển thị có thể là điểm quy đổi chứ không phải vote thô. Cần đọc thể lệ bình chọn để biết tỷ lệ.

## Ghi chú

- Repo công khai nên ai có link cũng xem được số liệu. Dữ liệu chỉ là số vote công khai trên trang bình chọn.
- Không cần xóa hay sửa file `data/history.jsonl`: đó là lịch sử các lần đo, dùng để tính tăng trưởng.
