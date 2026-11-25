# BFT65B — đã xác minh chuỗi liên tục Windows

**Không cần chạy lại BAT.** ZIP kết quả `20261119_192500_59bdf85e_GUI_LAI_CHO_CODEX.zip` đã được kiểm tra độc lập. Chuỗi raw → preparation mới → Part2A mới → Part2B mới → Part2C/PIT mới → development features mới đã hoàn tất, không fallback.

- 45/45 unit tests PASS trên đúng Windows engineering Python 3.13.9.
- 172 prepared Parquet trùng SHA references. Base/clean/PIT và ba bảng CSV Part2B/registry cũng trùng SHA.
- Development 1.231.631 dòng khớp schema/keys/giá trị; SHA byte khác.
- 179 datasets, 5.401 cột ngoài khóa, không có null/NaN/value mismatch trong comparisons đã đối chiếu.

Bộ này chứa code, raw-free execution evidence, báo cáo verification, checklist và manifest. Mở `REPRODUCTION_VERIFICATION_REPORT.md` và `REMAINING_ISSUES_CHECKLIST.md` để xem phạm vi chính xác. Raw Parquet/native metadata vẫn ở Windows; cloud kiểm logs/hashes/command lineage, không trực tiếp đọc lại raw files.

BAT và `run.py continuous` chỉ được giữ cho reviewer khi thật sự cần reproduction mới; không phải yêu cầu bạn lặp lại. Full clean-room Parts1–5/model E2E vẫn NOT EXECUTED. Không retrain HGB, đổi threshold, lặp ablation hoặc final-test inference. Public repository và report submission còn kiểm riêng; chưa viết report/Part 6.

Latest authoritative reviewer instructions: `docs/REPRODUCE_REVIEWER.md`. Run `python -B tools/reviewer_check.py --out ../BFT65B_REVIEW_NEW` on the actual public clone; do not use an old report draft.
