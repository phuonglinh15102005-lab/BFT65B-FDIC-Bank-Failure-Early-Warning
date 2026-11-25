> Historical upload guide, written before publication. Public HTTPS base clone passed 25 November 2026; see `REPORT_STATUS.md` for current status and `docs/REPRODUCE_REVIEWER.md` for current commands. Do not recreate the repository or rerun historical scientific stages.

# Hướng dẫn đẩy bộ BFT65B lên GitHub và nhờ Codex kiểm tra

**LƯU Ý:** Đây là ứng viên public-release đã được kiểm tra metadata/unit tests, **không phải** chứng nhận có thể tải FDIC từ đầu và tái chạy toàn bộ mô hình trên máy mới. Báo cáo Word/PDF được cung cấp riêng (không commit vào repo) **CHƯA CÓ GitHub URL thực tế**, nên bạn phải cập nhật trước khi nộp.

## Bước 1 — Tạo repository trống

Trên GitHub, chọn **New repository**, ví dụ `bft65b-fdic-bank-early-warning`; chọn **Public**. Không tick tạo README hoặc .gitignore vì gói này đã có.

## Bước 2 — Giải nén ZIP và đẩy TOÀN BỘ NỘI DUNG thư mục

Không upload ZIP thành một file trong GitHub. Vì có hàng trăm file, nên dùng Git thay vì kéo thả vào giao diện web.

Mở PowerShell tại thư mục đã giải nén (nơi thấy `run.py`, `README.md`):

```powershell
git init
git branch -M main
git add -A
git status
git commit -m "BFT65B integrated final review 20261125"
git remote add origin https://github.com/<YOUR_USERNAME>/<YOUR_REPO>.git
git push -u origin main
```

Thay phần `<YOUR_USERNAME>/<YOUR_REPO>` thành tên GitHub và repository **thật**. Nếu Git hỏi tên/email, cấu hình danh tính Git trong Settings rồi commit lại. Chỉ chạy `git push` sau khi đã rà soát file public, nhất là PDF chứa thông tin học viên.

## Bước 3 — Chạy Codex để soi bài

Mở **Codex** trong ChatGPT hoặc ứng dụng Codex với repo này, chọn branch `main`. Dán nội dung file `docs/CODEX_FINAL_REVIEW_PROMPT.md`. File `AGENTS.md` đã nêu phạm vi và guardrails. Bạn có thể yêu cầu `Review only, no changes` trước khi áp dụng sửa chữa.

Không cho Codex sửa frozen model selection, split, threshold, test scores hoặc log lịch sử chỉ để làm đẹp kết quả. Nếu Codex phát hiện sai khoa học, cần chỉ rõ bằng chứng và tách thay đổi code chưa chạy khỏi số đã chạy.

## Bước 4 — Fresh clone (thật sự kiểm tra bản công khai)

Từ thư mục khác trên máy tính:

```powershell
git clone https://github.com/<YOUR_USERNAME>/<YOUR_REPO>.git
cd <YOUR_REPO>
python -B -m unittest discover -s tests -q
python -B run.py plan
python -B run.py validate --out ..\bft65b_clone_validation
python -B tools/verify_e11_e12_aggregate.py
python -B tools/BFT65B_PUBLICATION_PRECHECK.py . --json ..\bft65b_privacy_scan.json
```

Xác nhận các lệnh không báo FAIL. Việc này kiểm tra metadata, mã nguồn và hash output đã gửi; **không** chứng minh end-to-end replay trên dữ liệu FDIC thực tế.

## Bước 5 — Hoàn thành báo cáo trước hạn

Mở `report/BFT65B_REPORT_FINAL_REVISED_20261125.docx`, thêm **URL GitHub public đã kiểm tra** lên trang đầu. Xuất lại PDF, kiểm trang **20 trang nội dung chính + tối đa 10 trang phụ lục**, thay tài liệu trong repo (nếu muốn công bố) và nộp report PDF/DOCX qua kênh yêu cầu của giảng viên. Link GitHub không được private hoặc lỗi, phải giữ public đến khi ra điểm.

## Những gì tuyệt đối không được upload

Dữ liệu FDIC gốc / Parquet, bank-level OOF/test predictions, fitted model binaries, raw response caches, file chứa mật khẩu/tokens, ZIP bằng chứng chưa kiểm duyệt. Tệp `.gitignore` đã chặn các đuôi phổ biến; đừng dùng `git add -f` để vượt qua.

## Trạng thái kiểm toán thực tế

- Mã nguồn 19/11: có archived Windows raw-snapshot-to-development replay; thiếu live acquisition/model end-to-end từ fresh anonymous clone.
- Có E11/E12 scripts và CSV aggregate đã hash-check, nhưng cần Parquet riêng trên Windows để tái tính kết quả từ dữ liệu.
- Các log public được thay đường dẫn người dùng bằng biến giả; bảng old/new SHA trong `provenance/PUBLIC_PATH_REDACTION_LEDGER.csv`; bản gốc giữ riêng tư.
- Codex và public-GitHub fresh clone **chưa được thực hiện tại thời điểm tạo gói**.

Latest authoritative reviewer instructions: `docs/REPRODUCE_REVIEWER.md`. Run `python -B tools/reviewer_check.py --out ../BFT65B_REVIEW_NEW` on the actual public clone; do not use an old report draft.
