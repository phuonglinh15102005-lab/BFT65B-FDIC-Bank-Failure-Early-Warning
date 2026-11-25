# BFT65B — kiểm toán và chỉnh sửa có chọn lọc 24/11/2026

## Phạm vi và quyết định
Bản gốc duy nhất: BFT65B_REPORT_SELECTIVE_FINAL_REVISION_20261123.docx (30 trang). Bản REVISED_FINAL_REPORT.docx của lượt chấm độc lập chỉ được dùng làm đối chiếu. Không thay nguyên văn hay bố cục bằng bản 29 trang. Bản mới giữ 34 bảng và 9 hình, Parts 1–6 và Appendix A–J. Không thay frozen protocol, feature set, HGB, seed, threshold hay held-out scores.

## Đối chiếu nhận xét
| Nhận xét | Kết luận độc lập và xử lý |
|---|---|
| A1 ZSTD level 3 mâu thuẫn | Đúng. storage_summary.json ghi zstd_level=3, row_group_size=100000, filter_year=2023, filter_quarter=1. Sửa Appendix F, ghi thêm OS cache không được flush và 66.61% tiết kiệm so với comparator CSV. |
| A2 cấu hình Spark action | Không đủ căn cứ để sửa thành default driver/four partitions. Có hai producer: 09_spark_action_benchmark.py dùng cores làm shuffle partitions, còn final_checks/09_spark_action_rebuild.py yêu cầu local[4], 8 partitions, 3g. Báo cáo lịch sử quy thời gian 1.527/3.864/1.316 s cho rebuilt action trial; JSON runtime của chính lượt action chưa có trong các archive đã đọc. Sửa văn bản để phân biệt cấu hình yêu cầu với effective setting chưa kiểm được; không đổi timings. |
| A3 URL GitHub | Đúng, vẫn mở. Không điền link giả hay ghi đã clone remote. |
| A4 Step05 | Dùng as-of canary trong nội dung nghiên cứu; giữ tên file đúng trong evidence index. |
| A5 Final HashAggregate | Đúng. PRIOR_SPARK_plan_final_decision_profile.txt có HashAggregate sau Exchange/AQE. Bổ sung vào Exhibit 3A. |
| A6 paired speedup | Đúng, archived figure_12_step07_paired_speedups.png xác định optimized pandas time / Polars time. Ghi rõ hướng tỷ số và khác biệt median paired vs ratio of medians. Không tự nhận đã tái tính trial-level khi ledger Step07 không có trong archive. |
| A7 Q1 | Đúng. Bổ sung lưu trữ theo quý + consolidated ZSTD Parquet, measured CSV comparator và tiêu chí Spark. |
| A8 nguồn ngoài | Văn bản hợp nhất 143/2026 ban hành 23/9/2026, WTO S/490, SBV Circular 31/2024 và 37/2025 có nguồn chính thức. LDR 107% không cần cho luận điểm crosswalk, bỏ câu khỏi thân bài vì không đóng góp trực tiếp (không phải vì nguồn giả). |
| 30 cột/equity baseline, thiếu t−1/growth | Đúng: đa biến 30 cột; equity-only một biến. Không có t−1 thì không có decision row; growth 1Q cần t−1/t−2, growth 4Q cần t−1/t−5, khoảng trống ở giữa không tự động gây null. Sửa thân bài và H2. |
| Failure stop / risk-set | Chấp nhận tên failure-linked risk stop, tránh ngụ ý 1.211 dòng đều sau đúng ngày FAILURE. Vintage và retrospective risk-set là rủi ro đối với chính backtest, không chỉ external validity. |
| Cost | Median COST dương 10.46626235 triệu USD, IQR 3.380–38.154 triệu USD, 2.330/2.410 events. r=20 do giả định 5%; J chỉ tính phí false first reviews, tất cả reviews tiêu tốn nhân lực. Không so J qua r khác nhau. Không dựng phí thực tế. |
| Overfit | AUC validation 0.9309–0.9649 hỗ trợ discrimination ngoài thời gian; không thể suy rằng train AUC dưới 0.982 loại trừ memorization, hoặc AP/lift chủ yếu do prevalence. Không dùng GroupKFold để phân rã nhân quả. |
| E12 AUC | Sửa chênh fold đầu +0.0018 từ các giá trị chưa làm tròn (0.9326355203−0.9308560536), không trừ các số đã làm tròn. Khoảng AP 0.2854–0.3035 đã đúng ở bản gốc. |
| Scale | scale_audit.json complete_measured_experiment=true, 12 combinations × 3 measured repeats. 2689.71 MiB/15.57 GiB≈16.9%; /6144 MiB≈43.8%. Không đưa ví dụ 390 năm vào: extrapolation theo số dòng không phải capacity benchmark. 70% RAM là illustrative migration trigger, không phải ngưỡng thực nghiệm. Spill chỉ là lý do profiling, không tự động biện minh cluster. |
| Calibration / peak capacity | Tái tính từ score ledger và first-review ledger gốc. Thêm phân bố 62 quý và tập trung positive decisions 2010–13. Giữ đối chứng Brier cố định từ dev. |
| Figure/table | Figure 1 heading trước hình, Figure 6 caption liền hình; Appendix J nằm trọn trang 30. Giữ 34 bảng, 9 hình. Sửa header tương phản thấp ở Table 8, E2, J4. |
| E10 | Đúng repo cũ thiếu thư mục. Phục hồi từ archive E10 gốc; 3 CSV và manifest khớp 4 hash; log/status chỉ redact prefix máy, ghi original/public hashes. Thêm verifier. |

## Kết quả tái tính read-only
Nguồn: BFT65B_WORK_REPORT_HANDOFF_V2_VERIFIED_20261118.zip, các thành viên final_test_scored_rows.csv.gz, final_test_first_alert_per_cert_year.csv.gz, locked_test_event_COST_join.csv. SHA-256 đầu vào ghi trong locked_policy_workload_and_metrics_audit.json. Không thực hiện inference.

- 364,440 rows / 1,112 positive; AP 0.434925073792; AUC 0.981620877746; Brier 0.002163292963; log loss 0.008750220557. Constant dev-rate Brier 0.003061801260.
- 2010–13: 117,658/364,440 rows = 32.2846%; 934/1,112 positives = 83.9928%. Pooled AP là metric của hỗn hợp thời kỳ, không đánh giá đồng đều các regime.
- 62 quý; 3,178 first reviews = 334 positive + 2,844 false; median 13/quý; quý cao nhất 2010Q1 765 reviews, 628 false; 24.0717% tổng review. Vì đây là quý đầu test với review ledger bắt đầu tại test, không suy rằng toàn bộ đỉnh do khủng hoảng; annual-first reset và boundary cũng ảnh hưởng số liệu. Không đánh đồng với staff-hours quan sát thực.
- 326/341=95.60% detected failures, COST coverage 40.9778%. Tỷ lệ large-bank COST coverage hiển thị 6.0% nhất quán J2.
- Cost audit gốc: median và IQR dương xác định dollar scale, không xác định độc lập r. Không chạy tối ưu policy mới.

## Nguồn chính thức được mở kiểm tra
- Công báo 143/2026/VBHN-LQ-VPQH: https://congbao.chinhphu.vn/van-ban/van-ban-hop-nhat-so-143-2026-vbhn-lq-vpqh-470556.htm
- WTO Trade Policy Review WT/TPR/S/490: https://www.wto.org/english/news_e/news_docs/S490.pdf — end-2025 4 state-owned, 27 joint-stock, 2 joint-venture, 9 wholly foreign-owned commercial banks. Illustrative 42, not a deduplicated regulatory roster.
- Banking Academy 2025 sector report: https://hvnh.edu.vn/nckh/vi/nghien-cuu-chuyen-de/vietnam-banking-sector-report-2025-11002.html
- Circular 31/2024: https://vanban.chinhphu.vn/?docid=210625&pageid=27160 ; Circular 37/2025: https://vanban.chinhphu.vn/?docid=215867&pageid=27160

## Rubric và việc còn mở
Không chuyển nguyên 87.25/95 sang bản mới hay cam kết 90/100. Đề có rubric định tính và điểm nội dung do giảng viên quyết định. Part 1–4 và 6 có bằng chứng mạnh; Part 5 cost-based criterion mới đạt một phần vì phí rà soát và tổn thất tránh được chưa đo; Reproducibility chưa đầy đủ vì anonymous public clone và fresh live-acquisition-to-test không được chứng minh. Leakage gate chưa có căn cứ xác nhận áp dụng, không đồng nghĩa loại trừ mọi rủi ro selection/vintage.

Trước hạn nộp: kiểm tra quyền công khai repository có tên/mã sinh viên; publish public; clone thật từ URL không dùng credential, chạy unit tests, plan, validate, các aggregate/hash verifier và privacy precheck; chèn URL thật trang 1, render lại 20+10; đồng bộ report trong đúng commit và nộp file qua kênh học phần, lưu receipt. Không cần huấn luyện lại HGB/chấm lại test hoặc E13 để xử lý các lỗi văn bản này.
