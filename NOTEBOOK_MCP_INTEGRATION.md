# Hướng dẫn Kết nối NotebookLM MCP với các Ứng dụng khác

NotebookLM MCP (Model Context Protocol) đã được cài đặt và cấu hình trên máy của bạn. Bạn có thể cho phép các trợ lý AI khác (như Claude Desktop, Cursor, Cursor, Windsurf, v.v.) truy cập vào dữ liệu NotebookLM của mình thông qua các phương thức sau.

## 1. Cấu hình Tự động (Khuyên dùng)

Công cụ `nlm` đã hỗ trợ sẵn việc tự động thêm cấu hình vào các ứng dụng phổ biến. Bạn chỉ cần mở terminal và chạy lệnh tương ứng:

| Ứng dụng | Câu lệnh thiết lập |
| :--- | :--- |
| **Claude Code** | `nlm setup add claude-code` |
| **Cursor** | `nlm setup add cursor` |
| **Windsurf** | `nlm setup add windsurf` |
| **Cline (VS Code)** | `nlm setup add cline` |
| **Tất cả các công cụ** | `nlm setup add all` (Quét và cài đặt cho mọi app được tìm thấy) |

*Lưu ý: Nếu lệnh `nlm` báo không tìm thấy, hãy sử dụng đường dẫn đầy đủ ở phần bên dưới.*

---

## 2. Cấu hình Thủ công (Dành cho các ứng dụng khác)

Nếu ứng dụng của bạn hỗ trợ MCP nhưng không có trong danh sách tự động, bạn có thể thêm thủ công vào file cấu hình của ứng dụng đó (thường là `mcp_config.json` hoặc phần settings của app).

### Thông tin Máy chủ MCP:

- **Command**: `C:\Users\ahhh\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\LocalCache\local-packages\Python313\Scripts\notebooklm-mcp.exe`
- **Args**: `[]` (Không cần tham số)

### Ví dụ cấu hình JSON:

```json
{
  "mcpServers": {
    "notebooklm": {
      "command": "C:\\Users\\ahhh\\AppData\\Local\\Packages\\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\\LocalCache\\local-packages\\Python313\\Scripts\\notebooklm-mcp.exe",
      "args": []
    }
  }
}
```

---

## 3. Các đường dẫn quan trọng trên máy của bạn

Nếu bạn cần gọi trực tiếp công cụ từ các script hoặc dịch vụ khác:

- **CLI Tool (nlm)**: `C:\Users\ahhh\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\LocalCache\local-packages\Python313\Scripts\nlm.exe`
- **MCP Server**: `C:\Users\ahhh\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\LocalCache\local-packages\Python313\Scripts\notebooklm-mcp.exe`

## 4. Kiểm tra trạng thái

Để kiểm tra xem máy chủ MCP có đang hoạt động tốt hay không, bạn có thể chạy:
`nlm doctor`

Để xem danh sách các notebook đang có:
`nlm notebook list`

---
*Tài liệu này được tạo tự động bởi Antigravity để hỗ trợ tích hợp hệ thống.*
