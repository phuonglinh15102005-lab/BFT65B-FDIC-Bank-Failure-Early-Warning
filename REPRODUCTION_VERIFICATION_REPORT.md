> Historical record, superseded for current execution status by `REPORT_STATUS.md` and S5 (25 November): second upstream replay, policy-only replay, four-layout storage sensitivity and both clean installs passed. Public clone and full E2E remain unverified.

# BFT65B — continuous reproduction verification đã đóng ngày 19/11/2026

## Kết luận

**VERIFIED trong phạm vi raw snapshot + cached HTTP sources → development features trên Windows.** Cả năm producer đã chạy trong cùng thư mục output mới và mọi parent trung gian đều mới. Independent returned-evidence review PASS. Không cần thêm lượt chạy Windows cho gate này. Full clean-room Parts1–5/model E2E, live acquisition, search/refit/final scoring vẫn NOT EXECUTED.

Windows run: `20261119_192500_59bdf85e`, bắt đầu 19:25 và kết thúc 19:29 ngày 19/11/2026 (Asia/Saigon). Uploaded ZIP SHA-256: `5dcd3b3c1faf9e520b2e8f5db7419d32717172147ba980d61bda8129fe2f31f4`. Executed source manifest: `e9fc39a0cc14cebda64c359cad8dd7cab3eaa251ff8f64fe988d9ef77f9d091e`.

## Bằng chứng thực thi và kiểm tra độc lập

Actual commands, cwd, versions, worker source hashes, parent input hashes trước/sau, output hashes và full comparisons nằm trong `release_evidence/continuous_windows_20261119/`. Toàn bộ 257 archived files được giữ nguyên bytes. `EXPORTED_FILE_MANIFEST.json` bao phủ đúng 256 files còn lại; reviewer đã tính lại đủ 256 SHA. Native Parquet và producer metadata JSON nằm ngoài ZIP theo chính sách giữ raw/private outputs trên Windows.

`INDEPENDENT_VERIFICATION.json` và code kiểm tra đi kèm trong `continuous_independent_review_20261119/` ghi actual audit command/environment/input-output hashes. Reviewer không chỉ đọc nhãn PASS: đã đối chiếu source/config identity, exact engineering runtime, argv đầy đủ, fresh-parent paths/hashes, embedded-vs-standalone results, detailed schema/key/null/NaN/value records, CSV-vs-JSON aggregates và pinned reference SHAs.

## Unit portability và environment

Python 3.13.9, NumPy 2.5.4, pandas 3.1.1, Polars 2.1.0, PyArrow 26.0.1 trùng profile đã ghi. 45/45 tests PASS trên Windows với normal startup, cwd đúng repo, không dùng -S. Lỗi unit test phụ thuộc sys.modules do QA nêu đã được xử lý và có bằng chứng trên môi trường mục tiêu. Các normal/-S/preload tests cloud trước đó được giữ nguyên scope, không đổi status lịch sử.

## Chuỗi parent mới

1. Raw FDIC snapshot và manifest → new preparation. Original raw ledger kiểm đúng scope 173 acquisition files; 170 quarter Financials + Institutions + Failures được chuẩn hóa.
2. New Part2A đọc new preparation. 193 prepared/report parent files có preservation records khớp outputs của stage trước; trong đó 172 prepared Parquet được so sánh với frozen references.
3. New Part2B đọc new Part2A. 28 parent identities khớp stage base; original native source SHA không đổi. Adapter chỉ đổi cache directory, không copy old outputs hoặc rewrite signatures.
4. New Part2C đọc new base + new Part2B. 59 tracked parent identities khớp outputs mới; native code tự kiểm fresh signatures/version/copies trước xử lý.
5. Part4 đọc new clean/PIT/registry sau PASS; ba input hashes trùng outputs của clean stage. Không fallback.

Fresh binding được reviewer tái đối chiếu từ exact argv và parent hash maps. Native input-signature checks được **thực thi bởi pinned producer source**, nhưng native summary/config JSON không được trả về nên reviewer **không tính lại riêng nội dung chữ ký native từ những JSON đó trên cloud**. Đây là ranh giới bằng chứng, không được mô tả thành một raw-data recomputation thứ hai.

## Kết quả số

| Dataset/scope | Số dòng hoặc số file | Kết quả |
|---|---:|---|
| Prepared quarterly Financials | 170 file; tổng 1.682.616 dòng | Từng file schema/keys/values và SHA trùng reference. |
| Prepared Institutions | 27.835 dòng | SHA và keyed comparison khớp. |
| Prepared Failures-all | 4.117 dòng | SHA khớp; SOURCE_ROW giữ legacy/unlinkable và event multiplicity. |
| Base | 1.682.616 dòng | SHA gốc tái tạo; keyed comparison khớp. |
| Part2B history | 59.901 dòng | Row-multiset và SHA CSV khớp. |
| Part2B exit evidence | 24.064 dòng | Row-multiset và SHA CSV khớp. |
| Clean | 1.669.802 dòng | SHA gốc tái tạo. |
| PIT | 1.629.398 dòng | SHA gốc tái tạo. |
| Event registry | 24.064 dòng | SHA CSV gốc tái tạo. |
| Development | 1.231.631 dòng | Schema/keys/values khớp; SHA byte khác. |

Tổng 179 datasets: 176 Parquet và 3 CSV. 178 trùng bytes với references. Cả 5.401 non-key column records có 0 null/NaN/value mismatch và max absolute delta 0, với đủ schema/key coverage. 170 financial-quarter rows cộng lại đúng 1.682.616; counts/column comparison CSVs được đối chiếu nguyên nội dung với JSON. Development được phép tolerance float 1e-9/1e-10 nhưng observed delta bằng 0. Không suy đoán nguyên nhân byte SHA khác và không gọi development byte-identical.

506 original-input identities khớp trước/sau: 173 raw files, 174 prepared-reference files, frozen output/Part2B references, cached bodies/metadata và raw ledger. Đây là hash records do Windows ghi, đã cross-check với các pinned anchors và archived outputs; raw files không được trực tiếp hash lại trên cloud. Raw ledger không có historical independent pre-pin; known prepared/output SHAs là anchor bổ sung.

## Những gì không được suy ra

Không có live acquisition, new hyperparameter search, HGB refit, threshold change, ablation repeat, model/CI/test metric recomputation hoặc final-test inference. Primary direction mean chronological AP rồi development-only cost policy giữ nguyên. R23/R24, model selection, prior Parts1–3/MLlib, ablation và posthoc CI không mở lại.

Không tuyên bố full E2E PASS hoặc hoàn tất submission. Clean dependency installation/historical native lock chưa thử; public GitHub URL/visibility/deadline, report identity/citations/AI acknowledgment và giới hạn 20+10 trang vẫn cần kiểm riêng. Historical filing vintages, assumptions về phí/r=20/avoidability, historical bootstrap provenance và ngày ablation muộn phải công bố. Không viết academic report/Part 6 ở đây.

## Bản release sau đóng gate

Source thực thi Windows được lưu bằng manifest/metadata/source snapshot riêng, không backdate. Bản mới chỉ cập nhật documentation, stage verification metadata và chức năng plan để phân biệt historical execution với việc plan tự nó không chạy dữ liệu. Các science producers và code chạy data không thay đổi. Metadata/package checks của bản mới có actual commands và hashes riêng.

Final metadata checks ran from /tmp using absolute entrypoints: plan and source validation PASS, 131 protected entries checked. The plan now separates its own non-executing invocation from protected historical Windows evidence. No data/model/unit suite was rerun for this status-only update. Exact executed pre-update controller bytes and source manifest are retained. Local publication inclusion and Git autocrlf byte-preservation checks also PASS; they do not prove GitHub publication.
