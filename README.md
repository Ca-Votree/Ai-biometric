# 🧬 AI Biometrics - Hệ Thống Điểm Danh Bằng Nhận Diện Khuôn Mặt

Hệ thống điểm danh tự động sử dụng AI nhận diện khuôn mặt, được xây dựng cho hội trường / lớp học. 
Backend sử dụng FastAPI; giao diện HTML/CSS/JS được phục vụ cùng origin để áp dụng kiểm soát truy cập thống nhất cho trang và API.

## 🏗️ Kiến Trúc

```
Camera → Frame Extraction → Face Detection (SCRFD) → Face Alignment 
→ Feature Extraction (ArcFace-512d) → FAISS Vector Search → API Backend ↔ Frontend
```

## ⚡ Tech Stack

- **Backend**: FastAPI + WebSocket + SQLite (dev)
- **AI Models**: InsightFace SCRFD (Detection) + ArcFace (Recognition) + FAISS (Vector DB)
- **Frontend**: Vanilla HTML/CSS/JS (Giao tiếp qua REST API & WebSocket)

---

## 🚀 Cài đặt & Chạy (Local)

Frontend được phục vụ cùng origin với API để backend có thể bảo vệ từng trang bằng phiên đăng nhập. Chỉ cần khởi động backend.

### 1. Khởi động Backend (Port 8000)

Sử dụng Anaconda/Miniconda (Khuyến nghị):

```bash
cd backend

# Tạo môi trường và cài dependencies
conda env create -f environment.yml

# Kích hoạt môi trường
conda activate biometrics

# Cấu hình biến môi trường
copy .env.example .env

# Mở backend/.env và đặt ADMIN_ID cùng ADMIN_PASSWORD
# ADMIN_PASSWORD cần ít nhất 12 ký tự; không dùng mật khẩu mẫu.

# Chạy API và frontend
python run.py
```
Truy cập `http://localhost:8000`. Không phục vụ trực tiếp thư mục `frontend/` bằng Live Server hoặc HTTP server tĩnh vì những server đó bỏ qua kiểm soát truy cập của backend.

### Tài khoản và quyền

- Khởi động lần đầu sẽ tạo tài khoản quản trị từ `ADMIN_ID` và `ADMIN_PASSWORD` trong `backend/.env`.
- Đăng nhập tại `/login?role=admin` hoặc `/login?role=teacher`. Cả hai cổng đăng nhập yêu cầu ID và mật khẩu; vai trò được kiểm tra ở backend.
- Sau khi đăng nhập, quản trị viên được chuyển đến `/admin.html`, giảng viên đến `/teacher.html`. Dashboard và các trang chức năng được tách theo vai trò; truy cập trang không đúng vai trò sẽ tự chuyển về dashboard được phép. `/` và `/index.html` tự điều hướng theo vai trò.
- Admin có dashboard tổng quan riêng tại `/admin.html`; tài khoản giảng viên, lớp/camera, sinh viên, lịch học, cấu hình, nhật ký và sao lưu được chia thành các trang quản lý riêng dưới `/admin-*.html`. Giảng viên chỉ có dashboard lớp, danh sách sinh viên chỉ đọc tại `/teacher-students.html`, giám sát camera và điểm danh.
- Quản trị viên có thể tạo, khóa/mở khóa và đặt lại mật khẩu giảng viên; phân công giảng viên vào lớp; cấu hình camera, lịch học, ngưỡng nhận diện và thời gian tính đi trễ.
- Giảng viên chỉ xem sinh viên, phiên điểm danh, lịch và báo cáo của các lớp được phân công. Quyền này được kiểm tra ở API, không chỉ ẩn nút trên giao diện.
- Giảng viên có thể rà soát điểm danh theo danh sách lớp, xác nhận/sửa trạng thái kèm lý do và xuất CSV. Thao tác quản trị, sửa điểm danh và xuất báo cáo được ghi nhật ký; phiên đã khóa không thể sửa.
- Quản trị viên quản lý hồ sơ sinh viên, đăng ký hoặc xóa dữ liệu khuôn mặt, xem nhật ký hoạt động và tải snapshot SQLite.
- Bản sao lưu SQLite không bao gồm thư mục ảnh khuôn mặt, chỉ mục FAISS hoặc log ứng dụng. Bảo vệ bản sao lưu vì cơ sở dữ liệu có thể chứa dữ liệu nhận diện; lưu các thành phần đó riêng theo quy trình an toàn.
- Ảnh/vector khuôn mặt chưa được tự động xóa theo thời hạn. Quản trị viên có thể xóa dữ liệu khuôn mặt thủ công; lưu trữ sinh viên cũng xóa ảnh/vector khỏi hệ thống đang chạy. Cần thống nhất chính sách lưu giữ và xử lý riêng các bản sao lưu trước khi bật xóa tự động.
- Các trang yêu cầu phiên đăng nhập; API và WebSocket cũng kiểm tra phiên/vai trò. Cookie phiên HttpOnly hết hạn sau 8 giờ.
- Với môi trường production, đặt `APP_ENV=production`, `SECRET_KEY` ngẫu nhiên tối thiểu 32 ký tự và `API_KEY`; cookie phiên sẽ dùng Secure. Sau khi tài khoản admin đầu tiên được tạo, có thể xóa `ADMIN_PASSWORD` khỏi môi trường.

---

## 📖 Hướng dẫn sử dụng

1. **Admin phân công lớp**: Tạo tài khoản giảng viên, cấu hình lớp và chọn giảng viên phụ trách.
2. **Admin quản lý sinh viên/lịch**: Thêm hồ sơ, đăng ký khuôn mặt và thiết lập lịch học.
3. **Giảng viên tạo phiên**: Chọn một trong các lớp được phân công, tạo phiên và mở camera của lớp.
4. **Rà soát điểm danh**: Kiểm tra danh sách, xác nhận hoặc sửa trạng thái với lý do, rồi khóa phiên khi hoàn tất.
5. **Báo cáo**: Lọc theo lớp/khoảng ngày và xuất CSV. Quản trị viên có thể xem nhật ký và tải snapshot cơ sở dữ liệu SQLite.

## 📁 Cấu trúc dự án mới

```
├── backend/           # Thư mục xử lý logic & AI Model (FastAPI)
│   ├── app/           # Mã nguồn API & AI pipeline
│   ├── models/        # AI model weights
│   ├── data/          # Database (SQLite), FAISS index, Logs
│   ├── run.py         # Script khởi động server
│   ├── environment.yml# Môi trường Conda
│   └── requirements.txt
├── frontend/          # Thư mục giao diện người dùng
│   ├── static/        # CSS, JS, Images (nếu có)
│   ├── admin.html             # Tổng quan quản trị
│   ├── admin-teachers.html    # Tài khoản giảng viên
│   ├── admin-classes.html     # Lớp học và camera
│   ├── admin-students.html    # Quản lý sinh viên
│   ├── admin-schedules.html  # Lịch học
│   ├── admin-settings.html   # Cấu hình hệ thống
│   ├── admin-audit.html      # Nhật ký hoạt động
│   ├── admin-backup.html     # Sao lưu
│   ├── teacher.html          # Dashboard giảng viên
│   ├── teacher-students.html # Danh sách sinh viên theo lớp (chỉ đọc)
│   ├── monitor.html          # Giám sát camera (giảng viên)
│   └── attendance.html       # Điểm danh (giảng viên)
└── README.md
```

## License

Dành cho nghiên cứu khoa học - Đề tài NCKH.
