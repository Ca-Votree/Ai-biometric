# Core Architecture & Modules

Tài liệu này tổng hợp các chú thích và kiến trúc hệ thống từ thư mục `app/core`.
Hệ thống AI Biometrics kết hợp tất cả các giai đoạn thành một pipeline hoàn chỉnh:
`Camera → Detection → Alignment → Extraction → Matching → Result`

## 1. Face Detector Module (`detector.py`)
- Sử dụng YOLO để phát hiện khuôn mặt trong ảnh.
- Output: Bounding boxes (và keypoints nếu có).
- Lưu ý: Thay thế SCRFD của InsightFace. Lớp `Face` cung cấp một mock tương tự như InsightFace's Face object.

## 2. Face Alignment Module (`aligner.py`)
- Căn chỉnh khuôn mặt về tư thế chuẩn dựa trên 5 facial landmarks.
- Sử dụng *affine transformation* (Umeyama algorithm) để normalize ảnh.
- Mục đích:
  - Giảm biến thiên do góc nghiêng, xoay đầu.
  - Chuẩn hóa đầu vào (ảnh 112x112) cho model trích xuất đặc trưng (ArcFace).

## 3. Feature Extractor Module (`extractor.py`)
- Trích xuất đặc trưng khuôn mặt (Embedding).
- Sử dụng model ArcFace ResNet100 (từ bộ `buffalo_l` của InsightFace) để tạo embedding vector 512 chiều.
- Đầu ra mặc định là L2 normalized embedding vector để so sánh dễ dàng bằng Cosine Similarity / Inner Product.

## 4. Face Matcher Module (`matcher.py`)
- Quản lý database vector và tìm kiếm danh tính (Faiss).
- Sử dụng FAISS IndexFlatIP (Inner Product) với normalized vectors, tương đương tính Cosine Similarity.
- Quy trình:
  1. Nhận embedding vector query 512 chiều.
  2. Lấy Top-K vectors gần nhất trong mảng Index.
  3. So sánh độ tương đồng (similarity) với mức cho phép (threshold) để đánh giá "Matched" hay "Unknown".

## 5. Liveness Manager (`liveness.py`)
- Module đánh giá độ sống (Anti-spoofing / Liveness) qua Challenge-Response.
- Môt số thử thách: Quay trái, quay phải, mỉm cười.
- Sử dụng 5 keypoints từ hệ thống và ước lượng tỷ lệ hình học (ví dụ: khoảng cách hai khóe miệng chia cho bề ngang hai mắt để nhận diện nụ cười).

## 6. Recognition Pipeline (`pipeline.py`)
- Quản lý luồng xử lý chính kết hợp tất cả các modules.
- Workflow chạy liên tục từng frame:
  1. Phát hiện khuôn mặt (Xài detector.py)
  2. Với mỗi khuôn mặt: Crop & Căn chỉnh ảnh (Xài aligner.py)
  3. Lấy Embedding (Xài extractor.py)
  4. Đối chiếu thông tin lấy Student_ID (Xài matcher.py)
  5. Tổng hợp ra kết quả (Annotated frame có vẽ bounding box).
