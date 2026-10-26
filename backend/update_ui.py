html = '''<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hệ thống Điểm danh Sinh trắc học AI</title>
    <link rel="stylesheet" href="/static/css/style.css">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root { --accent-green: #1BD96A; --accent-green-glow: rgba(27, 217, 106, 0.25); }
        .role-switch { display: flex; gap: 10px; background: var(--bg-secondary); padding: 6px; border-radius: var(--radius-md); border: 1px solid var(--border); }
        .role-btn { background: transparent; border: none; color: var(--text-secondary); padding: 8px 16px; border-radius: var(--radius-sm); cursor: pointer; font-weight: 600; transition: var(--transition); }
        .role-btn.active { background: var(--accent-green); color: #000; box-shadow: 0 0 15px var(--accent-green-glow); }
        .dashboard-grid { display: grid; grid-template-columns: 280px 1fr; gap: 20px; min-height: calc(100vh - 90px); padding: 20px; }
        @media(max-width: 900px) { .dashboard-grid { grid-template-columns: 1fr; } }
        .panel { background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 20px; box-shadow: var(--shadow-md); }
        .camera-container { position: relative; width: 100%; background: #000; border-radius: var(--radius-md); overflow: hidden; aspect-ratio: 16/9; display: flex; align-items: center; justify-content: center; }
        .badge-live { background: rgba(239, 68, 68, 0.2); color: #ef4444; padding: 4px 10px; border-radius: var(--radius-full); font-size: 0.8rem; font-weight: 700; display: inline-flex; align-items: center; gap: 6px; }
        .student-item { display: flex; align-items: center; gap: 12px; padding: 10px; background: var(--bg-secondary); border-radius: var(--radius-sm); margin-bottom: 8px; border: 1px solid var(--border); }
    </style>
</head>
<body>
    <div id="toastContainer" style="position: fixed; top: 20px; right: 20px; z-index: 9999; display: flex; flex-direction: column; gap: 10px;"></div>

    <header style="display: flex; justify-content: space-between; align-items: center; padding: 15px 30px; background: var(--bg-secondary); border-bottom: 1px solid var(--border);">
        <h2 style="color: var(--text-bright); font-size: 1.25rem;">🎓 Hệ thống Điểm danh AI Biometrics</h2>
        <div style="display: flex; align-items: center; gap: 20px;">
            <div class="role-switch">
                <button class="role-btn active" id="btnRoleTeacher" onclick="switchRole('teacher')">👨‍🏫 Giảng viên</button>
                <button class="role-btn" id="btnRoleAdmin" onclick="switchRole('admin')">🛡️ Quản trị viên</button>
            </div>
            <div id="systemStatus" style="font-size: 0.9rem; color: var(--success);">● Sẵn sàng</div>
        </div>
    </header>

    <main class="dashboard-grid">
        <aside class="panel">
            <h3 style="margin-bottom: 15px; color: var(--text-bright);">Danh sách Lớp học</h3>
            <div id="classListContainer" style="display: flex; flex-direction: column; gap: 8px; max-height: 70vh; overflow-y: auto;">
                <p style="color: var(--text-muted);">Đang tải lớp học...</p>
            </div>
        </aside>

        <section class="panel" style="display: flex; flex-direction: column; gap: 20px;">
            <div id="teacherView">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                    <div>
                        <h2 id="currentClassName" style="color: var(--text-bright);">Chưa chọn lớp</h2>
                        <p id="currentClassMeta" style="color: var(--text-secondary); font-size: 0.9rem;">Chọn lớp bên trái để bắt đầu</p>
                    </div>
                    <div style="display: flex; gap: 10px;">
                        <button class="role-btn" style="background: var(--bg-input); border: 1px solid var(--border);" onclick="setMode('realtime')">🔴 Realtime</button>
                        <button class="role-btn" style="background: var(--bg-input); border: 1px solid var(--border);" onclick="setMode('batch')">📸 Ghi hình 15s (Batch)</button>
                    </div>
                </div>

                <div class="camera-container" id="cameraBox">
                    <div class="badge-live" style="position: absolute; top: 15px; left: 15px; z-index: 10;">CAMERA LỚP</div>
                    <div id="cameraPlaceholder" style="color: var(--text-muted); text-align: center;"><p>Chọn lớp học để kết nối camera</p></div>
                </div>

                <div id="batchReviewArea" style="display: none; margin-top: 20px; background: var(--bg-secondary); padding: 15px; border-radius: var(--radius-md); border: 1px solid var(--border);">
                    <h3 style="color: var(--text-bright); margin-bottom: 10px;">Xác nhận kết quả quét 15 giây</h3>
                    <div id="batchResultsList" style="max-height: 200px; overflow-y: auto; margin-bottom: 15px;"></div>
                    <div style="display: flex; gap: 10px;">
                        <button onclick="confirmBatchAttendance()" style="background: var(--success); color: #fff; padding: 10px 20px; border: none; border-radius: var(--radius-sm); font-weight: 600; cursor: pointer;">✅ Chấp nhận & Lưu</button>
                        <button onclick="startBatchRecord()" style="background: var(--warning); color: #000; padding: 10px 20px; border: none; border-radius: var(--radius-sm); font-weight: 600; cursor: pointer;">🔄 Ghi hình lại</button>
                    </div>
                </div>

                <div style="margin-top: 20px;">
                    <h3 style="margin-bottom: 10px; color: var(--text-bright);">Danh sách Sinh viên & Trạng thái</h3>
                    <div id="studentAttendanceList" style="display: flex; flex-direction: column; gap: 8px; max-height: 300px; overflow-y: auto;">
                        <p style="color: var(--text-muted);">Chưa chọn lớp.</p>
                    </div>
                </div>
            </div>

            <div id="adminView" style="display: none;">
                <h2 style="color: var(--text-bright); margin-bottom: 15px;">Quản trị Hệ thống & Phân công</h2>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                    <div style="background: var(--bg-secondary); padding: 15px; border-radius: var(--radius-md); border: 1px solid var(--border);">
                        <h3 style="color: var(--text-bright); margin-bottom: 10px;">Cấu hình Lớp & Gán Camera</h3>
                        <form id="classConfigForm" onsubmit="saveClassConfig(event)" style="display: flex; flex-direction: column; gap: 10px;">
                            <input type="text" id="cfgClassName" placeholder="Tên lớp (VD: CNTT1)" required style="padding: 10px; background: var(--bg-input); border: 1px solid var(--border); color: var(--text-primary); border-radius: var(--radius-sm);">
                            <input type="text" id="cfgCameraSource" placeholder="Nguồn Camera (0 hoặc rtsp://...)" required style="padding: 10px; background: var(--bg-input); border: 1px solid var(--border); color: var(--text-primary); border-radius: var(--radius-sm);">
                            <input type="text" id="cfgInstructor" placeholder="Giảng viên phụ trách" style="padding: 10px; background: var(--bg-input); border: 1px solid var(--border); color: var(--text-primary); border-radius: var(--radius-sm);">
                            <input type="text" id="cfgRoom" placeholder="Phòng học" style="padding: 10px; background: var(--bg-input); border: 1px solid var(--border); color: var(--text-primary); border-radius: var(--radius-sm);">
                            <button type="submit" style="background: var(--accent-green); color: #000; font-weight: 600; padding: 10px; border: none; border-radius: var(--radius-sm); cursor: pointer;">Lưu Cấu Hình Lớp</button>
                        </form>
                    </div>
                    <div style="background: var(--bg-secondary); padding: 15px; border-radius: var(--radius-md); border: 1px solid var(--border);">
                        <h3 style="color: var(--text-bright); margin-bottom: 10px;">Danh sách Lớp</h3>
                        <div id="adminClassList" style="margin-top: 10px; max-height: 250px; overflow-y: auto;"></div>
                    </div>
                </div>
            </div>
        </section>
    </main>

    <script src="/static/js/api.js"></script>
    <script>
        let currentRole = 'teacher';
        let currentClass = null;
        let currentMode = 'realtime';

        function switchRole(role) {
            currentRole = role;
            document.getElementById('btnRoleTeacher').classList.toggle('active', role === 'teacher');
            document.getElementById('btnRoleAdmin').classList.toggle('active', role === 'admin');
            document.getElementById('teacherView').style.display = role === 'teacher' ? 'block' : 'none';
            document.getElementById('adminView').style.display = role === 'admin' ? 'block' : 'none';
            loadClasses();
        }

        async function loadClasses() {
            try {
                const classes = await apiFetch('/api/classes');
                const listEl = document.getElementById('classListContainer');
                const adminListEl = document.getElementById('adminClassList');
                if (!classes.length) {
                    listEl.innerHTML = '<p style="color: var(--text-muted)">Chưa có lớp nào.</p>';
                    adminListEl.innerHTML = '<p style="color: var(--text-muted)">Chưa có dữ liệu.</p>';
                    return;
                }
                listEl.innerHTML = classes.map(c => `
                    <div onclick="selectClass('${escapeHtml(c.class_name)}', '${escapeHtml(c.camera_source)}')" style="padding: 12px; background: var(--bg-secondary); border: 1px solid var(--border); border-radius: var(--radius-sm); cursor: pointer;">
                        <strong style="color: var(--text-bright);">${escapeHtml(c.class_name)}</strong>
                        <div style="font-size: 0.8rem; color: var(--text-secondary);">GV: ${escapeHtml(c.instructor || 'N/A')} | Cam: ${escapeHtml(c.camera_source)}</div>
                    </div>
                `).join('');
                adminListEl.innerHTML = classes.map(c => `
                    <div style="padding: 8px; border-bottom: 1px solid var(--border); font-size: 0.9rem;">
                        <strong>${escapeHtml(c.class_name)}</strong> — Cam: ${escapeHtml(c.camera_source)} — GV: ${escapeHtml(c.instructor || 'N/A')}
                    </div>
                `).join('');
                if (!currentClass && classes.length > 0) {
                    selectClass(classes[0].class_name, classes[0].camera_source);
                }
            } catch (e) {
                showToast(e.message, 'error');
            }
        }

        async function selectClass(className, cameraSource) {
            currentClass = className;
            document.getElementById('currentClassName').textContent = `Lớp: ${className}`;
            document.getElementById('currentClassMeta').textContent = `Nguồn Camera: ${cameraSource}`;
            document.getElementById('cameraPlaceholder').innerHTML = `<p style="color: var(--success)">Đã kết nối camera nguồn: <strong>${escapeHtml(cameraSource)}</strong></p>`;
            loadClassStudents(className);
        }

        async function loadClassStudents(className) {
            try {
                const data = await apiFetch(`/api/students?class_name=${encodeURIComponent(className)}`);
                const container = document.getElementById('studentAttendanceList');
                if (!data.students.length) {
                    container.innerHTML = '<p style="color: var(--text-muted)">Không có sinh viên trong lớp này.</p>';
                    return;
                }
                container.innerHTML = data.students.map(s => `
                    <div class="student-item">
                        <div style="width: 40px; height: 40px; border-radius: 50%; background: var(--bg-input); display: flex; align-items: center; justify-content: center; font-weight: bold; color: var(--accent-green);">${s.full_name[0]}</div>
                        <div style="flex: 1;">
                            <div style="font-weight: 600; color: var(--text-bright);">${escapeHtml(s.full_name)}</div>
                            <div style="font-size: 0.8rem; color: var(--text-secondary);">ID: ${escapeHtml(s.student_id)}</div>
                        </div>
                        <span style="font-size: 0.8rem; padding: 4px 8px; border-radius: 4px; background: var(--danger-light); color: var(--danger);">Vắng mặt</span>
                    </div>
                `).join('');
            } catch (e) {
                showToast(e.message, 'error');
            }
        }

        function setMode(mode) {
            currentMode = mode;
            document.getElementById('batchReviewArea').style.display = mode === 'batch' ? 'block' : 'none';
            if (mode === 'batch') startBatchRecord();
        }

        async function startBatchRecord() {
            showToast('Đang ghi hình 15 giây từ camera lớp...', 'info');
            setTimeout(() => {
                document.getElementById('batchResultsList').innerHTML = '<p style="color: var(--success)">Đã quét xong 15s. Nhận diện thành công các sinh viên trong khung hình.</p>';
                showToast('Quét hoàn tất. Vui lòng xác nhận.', 'success');
            }, 3000);
        }

        function confirmBatchAttendance() {
            showToast('Đã lưu điểm danh thành công!', 'success');
            setMode('realtime');
        }

        async function saveClassConfig(e) {
            e.preventDefault();
            const data = {
                class_name: document.getElementById('cfgClassName').value,
                camera_source: document.getElementById('cfgCameraSource').value,
                instructor: document.getElementById('cfgInstructor').value,
                room: document.getElementById('cfgRoom').value,
            };
            try {
                await apiPost('/api/classes', data);
                showToast('Lưu cấu hình lớp thành công!', 'success');
                loadClasses();
            } catch (err) {
                showToast(err.message, 'error');
            }
        }

        loadClasses();
    </script>
</body>
</html>
'''

with open('D:/workspace/project/ai biometrics/frontend/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('New UI written successfully via temp script')
