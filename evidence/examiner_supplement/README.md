# BFT65B supplementary checks for the examiner feedback

Giải nén rồi chạy trong thư mục có tệp README này. Cần Python 3.10+ với thư viện chuẩn; đã kiểm trên Python 3.12.14. Lệnh chỉ đọc các aggregate đi kèm và in JSON.

```sh
python -B verify_evidence.py
```

Nếu cần tệp mới để đối soát, dùng lệnh sau với một tên chưa tồn tại.

```sh
python -B verify_evidence.py --output my_verified_results.json
```

`verified_results.json` là kết quả đã chạy. `provenance.json` nêu tệp nguồn và SHA-256. `input_sha256.json` cho phép nhận ra input đã bị thay đổi. Các tính toán sử dụng số byte và null counts, hai bảng số lượng decision theo lag, bảng tổng hợp nhãn phát triển, nhật ký thời gian Step07 và bốn policy OOF đã đăng ký. Phần trăm CSV một byte là kịch bản số học giữ nguyên cách ghi mọi byte khác; không có một timing CSV mới. Mười hai cặp thời gian là cùng giao thức, cùng máy. Khoảng chi phí ở policy chỉ so bốn điểm đã có.

## E10 cho bản phát hành của sinh viên

`repository_addition/supplementary_diagnostics/E10/` chứa ba CSV tổng hợp nguyên gốc và hai JSON của lần chạy đã lưu, cùng README giải thích phạm vi. Khi chuẩn bị local candidate, có thể đặt riêng thư mục E10 tại đúng vị trí `supplementary_diagnostics/E10/` mà chỉ mục trỏ đến. Ba CSV và RUN_MANIFEST.json trùng từng byte với bốn SHA trong RUN_ACCEPTANCE.json. E10 về RBCRWAJ sử dụng panel không nhãn năm 2020–2021, còn các phân tích HGB chỉ dùng development. Các tài liệu riêng của sinh viên, raw snapshots và bank-level scores không được đóng gói.

Bản FINAL_SELECTIVE ngày 24/11 đã có đầy đủ E10. Ba CSV và hai JSON trong gói này giống hệt các bản đã kèm trong ZIP mới; không cần chép đè. Root README gọi cả 61 source là “byte-unchanged”, trong khi provenance/PUBLICATION_TRANSFORMATION.json ghi nhận một docstring preflight đã được lược thông tin riêng tư. Có thể thay riêng câu này bằng:

> The public release preserves the executed scientific procedures. A documented privacy edit changes one preflight script’s byte hash. The original and distributed digests appear in provenance/PUBLICATION_TRANSFORMATION.json.

Manifest của candidate gốc là hồ sơ lịch sử. Khi thêm tệp hoặc sửa README, tạo manifest cho phiên bản phân phối mới và kiểm lại đúng bản đó.

## Phép thử clone trong vòng chấm này

`local_clone_result.json` là kết quả thao tác thật trên một bản Git clone tạm của ZIP FINAL_SELECTIVE ngày 24/11. Môi trường Python mới không có dependency bên thứ ba. Unit suite 45/45, run.py plan, run.py validate (131 source files) và công cụ kiểm aggregate đều trả mã 0. Tất cả 902 mục trong manifest của bản gốc trùng hash sau clone. Sau khi chạy, working tree vẫn sạch. Phép thử này là local, không thể xác nhận quyền truy cập GitHub, và không thực hiện acquire/fit/score. Sau khi tác giả điền link thật, cần kiểm đúng public commit mới trong một clone khác.

Gói này hỗ trợ sửa bài và kiểm bằng chứng. Báo cáo chính và repository của sinh viên là các tài liệu riêng.
