# AI Biometrics Attendance System

Hệ thống điểm danh bằng nhận diện khuôn mặt, gồm backend FastAPI, giao diện web và pipeline xử lý ảnh. Tài liệu này hướng dẫn chuẩn bị môi trường, cấu hình, chạy ứng dụng và xử lý các lỗi cài đặt thường gặp.

## Mục lục

- [Tính năng](#tính-năng)
- [Kiến trúc và công nghệ](#kiến-trúc-và-công-nghệ)
- [Yêu cầu hệ thống](#yêu-cầu-hệ-thống)
- [Cài đặt](#cài-đặt)
- [Cấu hình](#cấu-hình)
- [Chạy ứng dụng](#chạy-ứng-dụng)
- [Tài khoản và phân quyền](#tài-khoản-và-phân-quyền)
- [Kiểm tra và API](#kiểm-tra-và-api)
- [Dữ liệu và quyền riêng tư](#dữ-liệu-và-quyền-riêng-tư)
- [Khắc phục sự cố](#khắc-phục-sự-cố)
- [Cấu trúc thư mục](#cấu-trúc-thư-mục)

## Tính năng

- Đăng nhập và phân quyền cho quản trị viên, giảng viên.
- Quản lý tài khoản giảng viên, lớp học, sinh viên và lịch học.
- Đăng ký, xóa dữ liệu khuôn mặt; nhận diện khuôn mặt để hỗ trợ điểm danh.
- Theo dõi camera, tạo và rà soát phiên điểm danh; cập nhật trạng thái có lý do.
- Xem báo cáo, xuất CSV, ghi nhật ký hoạt động và tải bản sao lưu SQLite.
- Cung cấp giao diện và API trên cùng một địa chỉ để áp dụng kiểm soát truy cập thống nhất.

## Kiến trúc và công nghệ

```text
Camera/ảnh → Phát hiện khuôn mặt (ONNX) → Căn chỉnh khuôn mặt
           → Trích xuất đặc trưng (InsightFace/ArcFace)
           → Tìm kiếm vector (FAISS) → FastAPI → Giao diện web
```

- **Backend:** Python, FastAPI, Uvicorn, SQLAlchemy.
- **Cơ sở dữ liệu:** SQLite mặc định; hỗ trợ cấu hình URL cơ sở dữ liệu qua biến môi trường.
- **Nhận diện:** ONNX Runtime, InsightFace, OpenCV, FAISS.
- **Frontend:** HTML, CSS và JavaScript; được backend phục vụ.

## Yêu cầu hệ thống

- Windows, Linux hoặc macOS.
- Python 3.10; khuyến nghị dùng Miniconda/Anaconda để cài các thư viện AI.
- Kết nối Internet trong lúc cài dependencies.
- Camera nếu cần điểm danh trực tiếp.
- Đủ dung lượng cho dependencies và các model AI.

> Bộ cài mặc định sử dụng `onnxruntime` và `faiss-cpu`. GPU không bắt buộc; cấu hình GPU cần các gói tương thích với phiên bản CUDA và driver đang dùng.

## Cài đặt

### 1. Lấy mã nguồn

Nếu chưa có mã nguồn trên máy:

```bash
git clone https://github.com/Ca-Votree/Ai-biometric.git
cd Ai-biometric
```

Nếu đã mở repository trên máy, chuyển tới thư mục gốc dự án thay vì clone lại.

### 2. Tạo môi trường Python

**Khuyến nghị — Conda:**

```bash
conda env create -f backend/environment.yml
conda activate biometrics
```

Nếu môi trường `biometrics` đã tồn tại, cập nhật môi trường từ file cấu hình:

```bash
conda env update -n biometrics -f backend/environment.yml
conda activate biometrics
```

**Lựa chọn khác — Python virtual environment:**

PowerShell:

```powershell
py -3.10 -m venv backend\.venv
backend\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt
```

Linux/macOS:

```bash
python3.10 -m venv backend/.venv
source backend/.venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt
```

Chỉ cần chọn **một** trong hai cách tạo môi trường trên. Nếu PowerShell chặn kích hoạt môi trường, có thể dùng trực tiếp `backend\.venv\Scripts\python.exe` thay cho `python` trong các lệnh tiếp theo.

### 3. Tạo file cấu hình

Tạo `backend/.env` từ file mẫu.

PowerShell:

```powershell
Copy-Item backend\.env.example backend\.env
```

Linux/macOS hoặc Git Bash:

```bash
cp backend/.env.example backend/.env
```

Mở `backend/.env` và đặt thông tin tài khoản quản trị, tối thiểu:

```dotenv
APP_ENV=development
DEBUG=true
ADMIN_ID=admin
ADMIN_PASSWORD=thay-bang-mat-khau-rieng-it-nhat-12-ky-tu
HOST=0.0.0.0
PORT=8000
```

`ADMIN_ID` chỉ được chứa chữ cái không dấu, chữ số, dấu chấm, gạch dưới hoặc gạch ngang. Mật khẩu quản trị phải có ít nhất 12 ký tự. Không dùng mật khẩu ví dụ ở trên cho môi trường thật.

### 4. Bổ sung model nhận diện

Các model không được lưu trong repository. Trước khi sử dụng chức năng nhận diện, hãy lấy model từ nguồn được phép sử dụng và đặt đúng các đường dẫn sau:

```text
backend/models/yolov8l-face-lindevs.onnx
backend/models/buffalo_l/w600k_r50.onnx
```

Model phát hiện khuôn mặt có thể đổi tên hoặc đường dẫn bằng `DETECTION_MODEL` trong `backend/.env`. Model nhận diện ArcFace hiện được ứng dụng đọc tại `backend/models/buffalo_l/w600k_r50.onnx`.

Backend tự tạo một số thư mục dữ liệu khi khởi động; việc tạo thư mục không thay thế các file model còn thiếu. Nếu thiếu model, ứng dụng có thể khởi động nhưng sẽ báo lỗi khi pipeline nhận diện được khởi tạo lần đầu.

## Cấu hình

Các biến được đọc từ `backend/.env`. Những cấu hình thường dùng:

- `APP_ENV`: môi trường chạy (`development` hoặc `production`); mặc định `development`.
- `DEBUG`: bật debug và log SQL; mặc định `true`.
- `ADMIN_ID`, `ADMIN_PASSWORD`: thông tin khởi tạo tài khoản quản trị; không đặt mặc định.
- `HOST`, `PORT`: địa chỉ bind và cổng HTTP; mặc định `0.0.0.0:8000`.
- `DATABASE_URL`: URL cơ sở dữ liệu; mặc định là SQLite.
- `CAMERA_SOURCE`: chỉ số camera hoặc URL luồng camera; mặc định `0`.
- `DETECTION_MODEL`: tên file model phát hiện trong `backend/models`; mặc định `yolov8l-face-lindevs.onnx`.
- `FACE_DETECTION_THRESHOLD`, `FACE_RECOGNITION_THRESHOLD`: ngưỡng phát hiện và khớp khuôn mặt; mặc định lần lượt là `0.5` và `0.45`.
- `API_KEY`: khóa API tùy chọn; bắt buộc khi chạy production.
- `SECRET_KEY`: khóa ký phiên; bắt buộc khi chạy production, tự sinh trong development.

Để triển khai production, đặt `APP_ENV=production`, cấu hình `SECRET_KEY` ngẫu nhiên có ít nhất 32 ký tự và đặt `API_KEY`. Cookie phiên sẽ bật thuộc tính `Secure`, do đó production cần được phục vụ qua HTTPS. Không commit file `.env` hoặc chia sẻ các khóa và mật khẩu.

## Chạy ứng dụng

Kích hoạt môi trường Python đã tạo, sau đó chạy từ thư mục `backend`:

```bash
cd backend
python run.py
```

Khi backend đã sẵn sàng, mở **http://localhost:8000** trong trình duyệt. Giao diện frontend được phục vụ cùng backend. Không mở trực tiếp file HTML hoặc chạy frontend bằng Live Server/server tĩnh riêng, vì cách đó không đi qua cơ chế xác thực và phân quyền của ứng dụng.

Dừng server bằng `Ctrl+C`. Nếu cần chạy bằng một lệnh từ thư mục gốc, có thể dùng:

```bash
python run_all.py
```

## Tài khoản và phân quyền

- Khi khởi động lần đầu, ứng dụng tạo tài khoản quản trị từ `ADMIN_ID` và `ADMIN_PASSWORD`. Sau khi tài khoản quản trị đã tồn tại trong cơ sở dữ liệu, hai biến này không còn bắt buộc để khởi động.
- Đăng nhập qua `/login?role=admin` hoặc `/login?role=teacher`. Giảng viên cần được quản trị viên tạo tài khoản.
- Quản trị viên quản lý giảng viên, lớp, camera, sinh viên, lịch học, cấu hình, nhật ký và bản sao lưu.
- Giảng viên truy cập các lớp được phân công, theo dõi camera và quản lý phiên điểm danh trong phạm vi quyền được cấp.
- Quyền được kiểm tra ở backend/API; không chỉ dựa vào việc ẩn các mục trên giao diện.
- Phiên đăng nhập được lưu trong cookie HttpOnly và hết hạn sau 8 giờ.

## Kiểm tra và API

- Kiểm tra trạng thái backend: **http://localhost:8000/api/health**
- Tài liệu OpenAPI/Swagger: **http://localhost:8000/docs**
- Kiểm tra cài đặt và khả năng sử dụng GPU (nếu cần):

  ```bash
  cd backend
  python check_gpu.py
  ```

`check_gpu.py` là tiện ích chẩn đoán; bộ dependencies mặc định hướng tới CPU. Để cấu hình GPU, tham khảo [GPU_SETUP_GUIDE.md](GPU_SETUP_GUIDE.md) và đảm bảo các phiên bản ONNX Runtime, FAISS, CUDA, driver tương thích với nhau.

## Dữ liệu và quyền riêng tư

- Dữ liệu ứng dụng mặc định nằm dưới `backend/data/`: cơ sở dữ liệu SQLite, ảnh khuôn mặt, chỉ mục FAISS và log.
- Các file `.env`, dữ liệu runtime và model được loại khỏi Git. Hãy sao lưu và bảo vệ chúng theo quy trình riêng.
- Bản sao lưu SQLite không bao gồm ảnh khuôn mặt, chỉ mục FAISS hoặc log. Cần sao lưu các thành phần này riêng nếu muốn khôi phục đầy đủ.
- Cơ sở dữ liệu và dữ liệu khuôn mặt có thể chứa thông tin nhạy cảm. Chỉ thu thập, sử dụng, lưu trữ và xóa dữ liệu theo chính sách được phê duyệt; giới hạn quyền truy cập và bảo vệ các bản sao lưu.

## Khắc phục sự cố

**Ứng dụng báo thiếu `ADMIN_ID` hoặc `ADMIN_PASSWORD`**

- Kiểm tra file `backend/.env` đã được tạo đúng vị trí và có giá trị chưa.
- Đặt mật khẩu dài ít nhất 12 ký tự; kiểm tra ID chỉ dùng các ký tự được hỗ trợ.
- Nếu đây là lần chạy đầu tiên, khởi động lại server sau khi sửa cấu hình.

**Không tìm thấy model hoặc lỗi khởi tạo nhận diện**

- Kiểm tra hai model có nằm đúng vị trí mô tả trong [Bổ sung model nhận diện](#4-bổ-sung-model-nhận-diện) không.
- Đảm bảo tên file khớp với `DETECTION_MODEL` và ứng dụng có quyền đọc các file.

**Không cài được dependency AI**

- Xác nhận đang sử dụng Python 3.10 và đã kích hoạt đúng môi trường.
- Ưu tiên tạo môi trường bằng `backend/environment.yml`; nếu lỗi vẫn xảy ra, kiểm tra phiên bản Python, hệ điều hành và thông báo lỗi của pip/Conda.

**Cổng 8000 đang được sử dụng**

- Đổi `PORT` trong `backend/.env`, sau đó truy cập `http://localhost:<cổng-mới>`.

**Không truy cập được camera**

- Kiểm tra `CAMERA_SOURCE` trong `backend/.env`, kết nối camera và quyền truy cập camera của hệ điều hành.
- Nếu dùng camera mạng, đặt `CAMERA_SOURCE` thành URL luồng mà máy chủ có thể truy cập.

**GPU không được sử dụng**

- Mặc định hệ thống có thể chạy bằng CPU. Kiểm tra driver/CUDA và cài đúng gói runtime GPU theo hướng dẫn GPU; `onnxruntime` hoặc `faiss-cpu` mặc định không cung cấp tăng tốc GPU.

## Cấu trúc thư mục

```text
.
├── backend/
│   ├── app/
│   │   ├── api/          # API và các route
│   │   ├── core/         # Pipeline nhận diện khuôn mặt
│   │   ├── database/     # Kết nối, model và thao tác cơ sở dữ liệu
│   │   └── services/     # Dịch vụ ứng dụng
│   ├── data/             # SQLite, ảnh, FAISS index và log (dữ liệu runtime)
│   ├── models/           # Model AI (không được commit)
│   ├── tests/            # Kiểm thử backend
│   ├── .env.example      # Mẫu cấu hình
│   ├── environment.yml   # Môi trường Conda
│   ├── requirements.txt  # Dependencies cài bằng pip
│   └── run.py            # Điểm khởi chạy backend
├── frontend/             # Các trang HTML và tài nguyên tĩnh
├── run_all.py            # Khởi chạy backend từ thư mục gốc
└── README.md
```

## Giấy phép và mục đích sử dụng

Dự án được xây dựng phục vụ nghiên cứu khoa học. Trước khi triển khai thực tế, cần đánh giá yêu cầu bảo mật, quyền riêng tư, sự đồng ý của người được ghi nhận và điều kiện cấp phép của từng model/phụ thuộc bên thứ ba.
