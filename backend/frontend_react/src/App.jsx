import React, { useState, useEffect } from 'react';
import { apiFetch, apiPost, apiPatch, apiDownload, apiPostFormData } from './services/api';
import './App.css';

export default function App() {
  const [theme, setTheme] = useState('dark');
  const [user, setUser] = useState(null);
  const [activeTab, setActiveTab] = useState('dashboard');
  const [classes, setClasses] = useState([]);
  const [selectedClass, setSelectedClass] = useState(null);
  const [students, setStudents] = useState([]);
  const [adminStudents, setAdminStudents] = useState([]);
  const [editingStudent, setEditingStudent] = useState(null);
  const [studentQuery, setStudentQuery] = useState('');
  const [toast, setToast] = useState(null);

  const [newStudent, setNewStudent] = useState({ student_id: '', full_name: '', class_name: '', file: null });
  const [newClass, setNewClass] = useState({ class_name: '', camera_source: '', instructor: '', room: '' });
  const [schedules, setSchedules] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [selectedSession, setSelectedSession] = useState(null);
  const [sessionRecords, setSessionRecords] = useState([]);
  const [newSchedule, setNewSchedule] = useState({ class_name: '', course_name: '', instructor: '', room: '', start_time: '', end_time: '' });

  const [loginRole, setLoginRole] = useState('teacher');
  const [loginId, setLoginId] = useState('GV01');
  const [loginPass, setLoginPass] = useState('123456');

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  useEffect(() => {
    if (user) loadClasses();
  }, [user]);

  useEffect(() => {
    if (selectedClass) loadStudents(selectedClass.class_name);
  }, [selectedClass]);

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  };

  const loadClasses = async () => {
    try {
      const data = await apiFetch('/api/classes');
      setClasses(data);
      if (data.length > 0 && !selectedClass) setSelectedClass(data[0]);
    } catch (e) {
      showToast(e.message, 'error');
    }
  };

  const loadStudents = async (className) => {
    try {
      const data = await apiFetch(`/api/students?class_name=${encodeURIComponent(className)}`);
      setStudents(data.students || []);
    } catch (e) {
      showToast(e.message, 'error');
    }
  };

  const loadAdminStudents = async () => {
    try {
      const data = await apiFetch('/api/students?limit=1000');
      setAdminStudents(data.students || []);
    } catch (e) {
      showToast(e.message, 'error');
    }
  };

  useEffect(() => {
    if (user?.role === 'admin' && activeTab === 'students') loadAdminStudents();
    if (activeTab === 'schedule') loadSchedules();
    if (activeTab === 'sessions') loadSessions();
  }, [user, activeTab]);

  const handleLogin = (e) => {
    e.preventDefault();
    setUser({ role: loginRole, name: loginId });
    showToast(`Đăng nhập thành công với quyền ${loginRole === 'admin' ? 'Quản trị viên' : 'Giảng viên'}`);
  };

  const handleAddStudent = async (e) => {
    e.preventDefault();
    try {
      const formData = new FormData();
      formData.append('student_id', newStudent.student_id);
      formData.append('full_name', newStudent.full_name);
      formData.append('class_name', newStudent.class_name || selectedClass?.class_name || '');
      if (newStudent.file) formData.append('file', newStudent.file);
      await apiPostFormData('/api/students', formData);
      showToast('Thêm sinh viên thành công!');
      setNewStudent({ student_id: '', full_name: '', class_name: '', file: null });
      if (selectedClass) loadStudents(selectedClass.class_name);
      loadAdminStudents();
    } catch (e) {
      showToast(e.message, 'error');
    }
  };

  const loadSchedules = async () => {
    try { const data = await apiFetch('/api/schedules'); setSchedules(data.schedules || []); } catch (e) { showToast(e.message, 'error'); }
  };

  const loadSessions = async () => {
    try { const data = await apiFetch('/api/attendance/sessions?limit=50'); setSessions(data.sessions || []); } catch (e) { showToast(e.message, 'error'); }
  };

  const handleAddSchedule = async (e) => {
    e.preventDefault();
    try {
      await apiPost('/api/schedules', { ...newSchedule, start_time: new Date(newSchedule.start_time).toISOString(), end_time: new Date(newSchedule.end_time).toISOString() });
      showToast('Đã tạo lịch học'); setNewSchedule({ class_name: '', course_name: '', instructor: '', room: '', start_time: '', end_time: '' }); loadSchedules();
    } catch (e) { showToast(e.message, 'error'); }
  };

  const startScheduledSession = async (scheduleId) => {
    try { await apiPost('/api/attendance/sessions/from-schedule', { schedule_id: scheduleId }); showToast('Đã tạo phiên điểm danh'); loadSessions(); }
    catch (e) { showToast(e.message, 'error'); }
  };

  const openSession = async (session) => {
    try {
      const data = await apiFetch(`/api/attendance/sessions/${session.id}/records`);
      setSelectedSession(session); setSessionRecords(data.records || []);
    } catch (e) { showToast(e.message, 'error'); }
  };

  const decideRecord = async (record, status) => {
    try {
      await apiPatch(`/api/attendance/sessions/${selectedSession.id}/records/${record.student_id}`, { status });
      setSessionRecords(sessionRecords.map(x => x.student_id === record.student_id ? {...x, status} : x));
      showToast('Đã cập nhật kết quả duyệt');
    } catch (e) { showToast(e.message, 'error'); }
  };

  const handleAddClass = async (e) => {
    e.preventDefault();
    try {
      await apiPost('/api/classes', newClass);
      showToast('Thêm lớp học thành công!');
      setNewClass({ class_name: '', camera_source: '', instructor: '', room: '' });
      loadClasses();
    } catch (e) { showToast(e.message, 'error'); }
  };

  if (!user) {
    return (
      <div className="login-wrapper">
        <div className="login-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
            <h2>🎓 Đăng nhập Hệ thống</h2>
            <button onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')} className="btn-secondary">
              {theme === 'dark' ? '☀️ Sáng' : '🌙 Tối'}
            </button>
          </div>
          <div className="role-tabs">
            <button className={`role-tab ${loginRole === 'teacher' ? 'active' : ''}`} onClick={() => setLoginRole('teacher')}>👨‍🏫 Giảng viên</button>
            <button className={`role-tab ${loginRole === 'admin' ? 'active' : ''}`} onClick={() => setLoginRole('admin')}>🛡️ Quản trị viên</button>
          </div>
          <form onSubmit={handleLogin}>
            <div className="form-group">
              <label>{loginRole === 'admin' ? 'Tài khoản Admin' : 'Mã Giảng Viên (ID)'}</label>
              <input type="text" className="input" value={loginId} onChange={e => setLoginId(e.target.value)} required />
            </div>
            <div className="form-group">
              <label>Mật khẩu</label>
              <input type="password" className="input" value={loginPass} onChange={e => setLoginPass(e.target.value)} required />
            </div>
            <button type="submit" className="btn-primary" style={{ width: '100%' }}>Đăng nhập</button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="app-container">
      {toast && <div className={`toast ${toast.type}`}>{toast.msg}</div>}
      <aside className="sidebar">
        <div className="sidebar-brand">
          <h3>🎓 AI Biometrics</h3>
          <span className="badge-role">{user.role === 'admin' ? 'Quản trị viên' : 'Giảng viên'}</span>
        </div>
        <nav className="nav-menu">
          <button className={`nav-item ${activeTab === 'dashboard' ? 'active' : ''}`} onClick={() => setActiveTab('dashboard')}>📊 Tổng quan & Điểm danh</button>
          <button className={`nav-item ${activeTab === 'schedule' ? 'active' : ''}`} onClick={() => setActiveTab('schedule')}>🗓️ Lịch học</button>
          <button className={`nav-item ${activeTab === 'sessions' ? 'active' : ''}`} onClick={() => setActiveTab('sessions')}>✅ Duyệt phiên điểm danh</button>
          {user.role === 'admin' && (
            <>
              <button className={`nav-item ${activeTab === 'students' ? 'active' : ''}`} onClick={() => setActiveTab('students')}>👥 Quản lý Sinh viên</button>
              <button className={`nav-item ${activeTab === 'classes' ? 'active' : ''}`} onClick={() => setActiveTab('classes')}>🏫 Quản lý Lớp & Camera</button>
            </>
          )}
        </nav>
        <div style={{ marginTop: 'auto', padding: 15 }}>
          <button onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')} className="btn-secondary" style={{ width: '100%', marginBottom: 10 }}>{theme === 'dark' ? '☀️ Sáng' : '🌙 Tối'}</button>
          <button onClick={() => setUser(null)} className="btn-danger" style={{ width: '100%' }}>Đăng xuất</button>
        </div>
      </aside>
      <main className="main-content">
        <header className="topbar">
          <h2>{activeTab === 'dashboard' ? 'Bảng điều khiển điểm danh' : activeTab === 'students' ? 'Quản lý danh sách sinh viên' : activeTab === 'schedule' ? 'Lịch học' : activeTab === 'sessions' ? 'Duyệt phiên điểm danh' : 'Cấu hình lớp học & camera'}</h2>
          <div>Xin chào, <strong>{user.name}</strong></div>
        </header>
        <div className="content-body">
          {activeTab === 'dashboard' && (
            <div className="dashboard-grid">
              <div className="panel">
                <h3>Danh sách Lớp học phụ trách</h3>
                <div className="class-list">
                  {classes.map(c => (
                    <div key={c.class_name} className={`class-card ${selectedClass?.class_name === c.class_name ? 'active' : ''}`} onClick={() => setSelectedClass(c)}>
                      <h4>{c.class_name}</h4>
                      <p>GV: {c.instructor || 'Chưa phân công'} | Cam: {c.camera_source}</p>
                    </div>
                  ))}
                </div>
              </div>
              <div className="panel">
                <h3>Danh sách Sinh viên & Trạng thái ({selectedClass?.class_name})</h3>
                <div className="student-list" style={{ marginTop: 15 }}>
                  {students.map(s => (
                    <div key={s.student_id} className="student-row">
                      <div className="avatar">{s.full_name[0]}</div>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: 600 }}>{s.full_name}</div>
                        <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>ID: {s.student_id}</div>
                      </div>
                      <span className="status-badge absent">Vắng mặt</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
          {activeTab === 'schedule' && (
            <div className="panel">
              <h3>Lịch học và tạo phiên điểm danh</h3>
              {user.role === 'admin' && <form onSubmit={handleAddSchedule} className="schedule-form">
                {['class_name','course_name','instructor','room'].map(key => <input key={key} className="input" placeholder={{class_name:'Lớp',course_name:'Môn học',instructor:'Giảng viên',room:'Phòng'}[key]} value={newSchedule[key]} onChange={e => setNewSchedule({...newSchedule, [key]: e.target.value})} required={key === 'class_name' || key === 'course_name'} />)}
                <input className="input" type="datetime-local" value={newSchedule.start_time} onChange={e => setNewSchedule({...newSchedule, start_time: e.target.value})} required />
                <input className="input" type="datetime-local" value={newSchedule.end_time} onChange={e => setNewSchedule({...newSchedule, end_time: e.target.value})} required />
                <button className="btn-primary">Tạo lịch</button>
              </form>}
              <table className="data-table"><thead><tr><th>Lớp</th><th>Môn học</th><th>Thời gian</th><th>Thao tác</th></tr></thead><tbody>
                {schedules.map(s => <tr key={s.id}><td>{s.class_name}</td><td>{s.course_name}</td><td>{new Date(s.start_time).toLocaleString('vi-VN')}</td><td><button className="btn-primary" onClick={() => startScheduledSession(s.id)}>Tạo phiên</button></td></tr>)}
              </tbody></table>
            </div>
          )}
          {activeTab === 'sessions' && (
            <div className="panel">
              <h3>Duyệt và khóa phiên điểm danh</h3>
              <table className="data-table"><thead><tr><th>Phiên</th><th>Lớp</th><th>Trạng thái</th><th>Đã nhận diện</th><th>Thao tác</th></tr></thead><tbody>
                {sessions.map(s => <tr key={s.id}><td>{s.session_name}</td><td>{s.class_name || '—'}</td><td>{s.status || 'open'}</td><td>{s.total_recognized}</td><td><button className="btn-secondary" onClick={() => openSession(s)}>Xem kết quả</button> <button className="btn-secondary" onClick={() => apiPatch(`/api/attendance/sessions/${s.id}/status`, {status:'review'}).then(() => { showToast('Đã chuyển sang duyệt'); loadSessions(); })}>Duyệt</button> <button className="btn-primary" onClick={() => apiPatch(`/api/attendance/sessions/${s.id}/status`, {status:'locked'}).then(() => { showToast('Đã khóa phiên'); loadSessions(); })}>Khóa</button> <button className="btn-secondary" onClick={() => apiDownload(`/api/attendance/sessions/${s.id}/export.csv`)}>CSV</button></td></tr>)}
              </tbody></table>
              {selectedSession && <div className="panel" style={{ marginTop: 20 }}><h3>Kết quả: {selectedSession.session_name}</h3><table className="data-table"><thead><tr><th>Mã SV</th><th>Họ tên</th><th>Độ tương đồng</th><th>Trạng thái</th><th>Duyệt</th></tr></thead><tbody>
                {sessionRecords.map(r => <tr key={r.student_id}><td>{r.student_id}</td><td>{r.full_name}</td><td>{r.similarity_score?.toFixed?.(3) || '—'}</td><td>{r.status || 'pending'}</td><td><button className="btn-primary" onClick={() => decideRecord(r, 'present')}>Có mặt</button> <button className="btn-danger" onClick={() => decideRecord(r, 'rejected')}>Từ chối</button></td></tr>)}
              </tbody></table></div>}
            </div>
          )}
          {activeTab === 'students' && user.role === 'admin' && (
            <div className="panel">
              <h3>Quản lý Sinh viên & Đăng ký Khuôn mặt</h3>
              <input className="input" style={{ marginTop: 15, marginBottom: 12 }} placeholder="Tìm theo mã, họ tên hoặc lớp..." value={studentQuery} onChange={e => setStudentQuery(e.target.value)} />
              <form onSubmit={handleAddStudent} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr auto', gap: 10, marginTop: 15, marginBottom: 25 }}>
                <input type="text" className="input" placeholder="Mã SV" value={newStudent.student_id} onChange={e => setNewStudent({...newStudent, student_id: e.target.value})} required />
                <input type="text" className="input" placeholder="Họ tên" value={newStudent.full_name} onChange={e => setNewStudent({...newStudent, full_name: e.target.value})} required />
                <input type="text" className="input" placeholder="Lớp" value={newStudent.class_name} onChange={e => setNewStudent({...newStudent, class_name: e.target.value})} required />
                <input type="file" className="input" accept="image/*" onChange={e => setNewStudent({...newStudent, file: e.target.files[0]})} />
                <button type="submit" className="btn-primary">Thêm</button>
              </form>
              <table className="data-table">
                <thead><tr><th>Mã SV</th><th>Họ tên</th><th>Lớp</th><th>Trạng thái</th><th>Thao tác</th></tr></thead>
                <tbody>
                  {adminStudents.filter(s => `${s.student_id} ${s.full_name} ${s.class_name || ''}`.toLowerCase().includes(studentQuery.toLowerCase())).map(s => (
                    <tr key={s.student_id}>
                      <td>{s.student_id}</td><td>{s.full_name}</td><td>{s.class_name || '—'}</td>
                      <td><span style={{ color: s.face_registered ? 'var(--success)' : 'var(--warning)' }}>{s.face_registered ? '● Đã đăng ký' : '○ Chưa đăng ký'}</span></td>
                      <td><button className="btn-danger" onClick={async () => { if (!confirm(`Vô hiệu hóa ${s.full_name}?`)) return; await apiFetch(`/api/students/${s.student_id}`, { method: 'DELETE' }); showToast('Đã vô hiệu hóa sinh viên'); loadAdminStudents(); }}>Xóa</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {activeTab === 'classes' && user.role === 'admin' && (
            <div className="panel">
              <h3>Cấu hình Lớp học & Camera</h3>
              <form onSubmit={handleAddClass} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr auto', gap: 10, marginTop: 15, marginBottom: 25 }}>
                <input type="text" className="input" placeholder="Tên lớp" value={newClass.class_name} onChange={e => setNewClass({...newClass, class_name: e.target.value})} required />
                <input type="text" className="input" placeholder="Camera Source" value={newClass.camera_source} onChange={e => setNewClass({...newClass, camera_source: e.target.value})} required />
                <input type="text" className="input" placeholder="Giảng viên" value={newClass.instructor} onChange={e => setNewClass({...newClass, instructor: e.target.value})} />
                <input type="text" className="input" placeholder="Phòng" value={newClass.room} onChange={e => setNewClass({...newClass, room: e.target.value})} />
                <button type="submit" className="btn-primary">Lưu</button>
              </form>
              <table className="data-table">
                <thead><tr><th>Lớp</th><th>Camera</th><th>GV</th><th>Phòng</th></tr></thead>
                <tbody>
                  {classes.map(c => (
                    <tr key={c.class_name}><td>{c.class_name}</td><td>{c.camera_source}</td><td>{c.instructor}</td><td>{c.room}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}