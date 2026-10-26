# Giải thích chi tiết Backend Core - AI Biometrics System

Phần `core` là "trái tim" của hệ thống, chịu trách nhiệm xử lý toàn bộ luồng dữ liệu từ hình ảnh thô đến kết quả nhận diện danh tính sinh viên.

## 1. Kiến trúc Pipeline ([pipeline.py](cci:7://file:///d:/project/ai%20biometrics/backend/app/core/pipeline.py:0:0-0:0))
Hệ thống sử dụng một Pipeline tuần tự để xử lý mỗi khung hình (frame) từ camera:
1. **Detection (Phát hiện):** Tìm vị trí các khuôn mặt trong ảnh.
2. **Alignment (Căn chỉnh):** Xoay và chuẩn hóa khuôn mặt về góc nhìn thẳng.
3. **Extraction (Trích xuất):** Chuyển đổi hình ảnh khuôn mặt thành một vector số học (512 chiều).
4. **Matching (So sánh):** So khớp vector vừa trích xuất với cơ sở dữ liệu để tìm danh tính.

## 2. Các thành phần AI chính (InsightFace)
Chúng ta sử dụng thư viện **InsightFace**, một Framework nhận diện khuôn mặt hàng đầu hiện nay:

*   **Detector (SCRFD):** Sử dụng model SCRFD (Sample and Computation Redistribution for Efficient Face Detection). Đây là model cực kỳ nhanh và chính xác, có thể phát hiện nhiều khuôn mặt cùng lúc ngay cả khi bị che khuất một phần.
*   **Extractor (ArcFace):** Sử dụng model ArcFace để trích xuất Feature Embedding. Nó biến đặc điểm khuôn mặt thành một "vân tay số" (vector 512 chiều). Hai ảnh của cùng một người sẽ có hai vector nằm rất gần nhau trong không gian vector.

## 3. Công cụ tìm kiếm Vector (FAISS)
Để hệ thống có thể hoạt động nhanh ngay cả khi có hàng ngàn sinh viên, chúng ta sử dụng **FAISS (Facebook AI Similarity Search)**:
*   **IndexFlatIP:** Chúng ta sử dụng chuẩn `Inner Product` kết hợp với các vector đã được chuẩn hóa (L2 Normalized), điều này tương đương với việc tính toán **Cosine Similarity**.
*   **Tốc độ:** FAISS cho phép tìm kiếm người có khuôn mặt giống nhất trong chưa đầy 1ms.
*   **ID Mapping:** Vì FAISS chỉ lưu vector và số index (0, 1, 2...), chúng ta có một file `id_map.json` để ánh xạ index đó ngược lại mã sinh viên (`student_id`).

## 4. Các luồng xử lý quan trọng

### Luồng Nhận diện (Inference)
1. Frame từ camera được gửi vào [RecognitionPipeline](cci:2://file:///d:/project/ai%20biometrics/backend/app/core/pipeline.py:54:0-286:59).
2. `face_detector` tìm các khuôn mặt và trả về tọa độ (bbox) + các điểm mốc (landmarks).
3. Với mỗi khuôn mặt, `feature_extractor` tạo ra một vector embedding.
4. `face_matcher` cầm vector đó "hỏi" FAISS xem ai là người giống nhất.
5. Nếu độ tương đồng (similarity) > 0.6 (ngưỡng mặc định), hệ thống xác nhận danh tính.

### Luồng Đăng ký (Registration)
1. Người dùng gửi một hoặc nhiều ảnh của sinh viên mới.
2. Pipeline trích xuất vector từ tất cả ảnh đó.
3. **Centroid Embedding:** Hệ thống tính toán vector trung bình từ các ảnh để tạo ra một "đại diện" chuẩn nhất cho sinh viên đó.
4. Vector trung bình này được thêm vào FAISS và lưu xuống đĩa (`faiss_index.bin`).

## 5. Tối ưu hóa hiệu năng
*   **Lazy Loading:** Các model AI chỉ được tải vào RAM khi có yêu cầu nhận diện đầu tiên để tiết kiệm tài nguyên lúc khởi động.
*   **Async/Await:** Backend FastAPI xử lý các yêu cầu IO-bound (database, log) một cách bất đồng bộ để không làm nghẽn luồng xử lý AI.
*   **Batch Processing:** Hỗ trợ trích xuất đặc điểm theo lô để tăng tốc độ khi đăng ký nhiều sinh viên cùng lúc.
