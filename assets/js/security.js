/**
 * IELTS Mastery - Advanced Security System
 * Protected by Phạm Tiến Dũng
 */

(function() {
    // 1. Chặn chuột phải
    document.addEventListener('contextmenu', e => e.preventDefault());

    // 2. Chặn các phím tắt quan trọng (F12, Ctrl+U, Ctrl+Shift+I, Ctrl+S)
    document.addEventListener('keydown', function(e) {
        if (
            e.key === 'F12' || 
            (e.ctrlKey && e.shiftKey && e.key === 'I') || 
            (e.ctrlKey && e.shiftKey && e.key === 'C') || 
            (e.ctrlKey && e.shiftKey && e.key === 'J') || 
            (e.ctrlKey && e.key === 'u') || 
            (e.ctrlKey && e.key === 's')
        ) {
            e.preventDefault();
            return false;
        }
    });

    // 3. Chặn bôi đen nội dung (trừ các ô input/textarea)
    document.addEventListener('selectstart', e => {
        if (!e.target.tagName.match(/INPUT|TEXTAREA/i)) {
            e.preventDefault();
        }
    });

    // 4. DevTools Detection & Anti-Debugging
    // Khi người dùng cố tình mở Console, dòng này sẽ kích hoạt bẫy debugger liên tục
    setInterval(function() {
        const startTime = performance.now();
        debugger;
        const endTime = performance.now();
        if (endTime - startTime > 100) {
            // Nếu phát hiện bị dừng lại bởi debugger (DevTools đang mở)
            document.body.innerHTML = `
                <div style="height:100vh; display:flex; flex-direction:column; align-items:center; justify-content:center; background:#0f172a; color:#f8fafc; font-family:sans-serif; text-align:center; padding:20px;">
                    <h1 style="font-size:3rem; margin-bottom:1rem;">🛡️ Chế độ bảo mật kích hoạt</h1>
                    <p style="font-size:1.2rem; opacity:0.7;">Vui lòng đóng Developer Tools để tiếp tục học tập. Bản quyền thuộc về Phạm Tiến Dũng.</p>
                    <button onclick="location.reload()" style="margin-top:2rem; padding:12px 24px; background:#2563eb; border:none; color:white; border-radius:12px; cursor:pointer; font-weight:bold;">Tải lại trang</button>
                </div>
            `;
        }
    }, 1000);

    // 5. Chặn việc tải trang về máy thông qua các script lạ
    if (window.location.protocol === 'file:') {
        document.body.innerHTML = "<h1>Vui lòng truy cập trực tiếp từ website chính thức để bảo mật dữ liệu.</h1>";
    }

    // 6. Console Poisoning - Xóa sạch log nếu có người cố hack
    console.log("%cDừng lại!", "color: red; font-size: 50px; font-weight: bold; -webkit-text-stroke: 1px black;");
    console.log("%cNội dung này được bảo vệ bởi Phạm Tiến Dũng. Mọi hành vi sao chép trái phép sẽ bị truy cứu.", "font-size: 20px;");
    
    // Vô hiệu hóa console khi không ở chế độ dev
    if (!window.location.hostname.includes('localhost') && !window.location.hostname.includes('127.0.0.1')) {
        const noop = () => {};
        // console.log = noop;
        // console.warn = noop;
        // console.error = noop;
    }
})();
