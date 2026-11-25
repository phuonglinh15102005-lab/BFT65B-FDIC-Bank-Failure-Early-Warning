> Historical record, superseded for current execution status by `REPORT_STATUS.md` and S5 (25 November): second upstream replay, policy-only replay, four-layout storage sensitivity and both clean installs passed. Public clone and full E2E remain unverified.

> Current status: the 19 November continuous Windows run has now been reviewed. No further user rerun is requested. See REPRODUCTION_VERIFICATION_REPORT.md and REMAINING_ISSUES_CHECKLIST.md; the text below preserves earlier history.

> **Superseded for current reproducibility status:** this document preserves the earlier checkpoint-release history. The new QA discrepancy is addressed by `REPRODUCTION_VERIFICATION_REPORT.md`, `REMAINING_ISSUES_CHECKLIST.md` and the root README. Prior checkpoint PASS does not prove the new continuous chain; one new upstream-only Windows run is required.

# Kiểm toán reproducibility cuối của code release

Ngày chốt: 19/11/2026. Mục tiêu là hoàn thiện source và quy trình nộp Parts 1–5; không mở lại mô hình hoặc viết báo cáo học thuật.

## Kết luận trong phạm vi bằng chứng

Source release đã qua kiểm tra cú pháp, resources, protocol/hash, policies và các contract tests cuối. **Ba producer mới đã chạy trên Windows và returned evidence đã qua đối chiếu độc lập; full clean-room E2E vẫn NOT EXECUTED.** Không còn lỗi nào được phát hiện trong các kiểm tra code đã chạy không đồng nghĩa đã loại trừ mọi lỗi runtime.

Giữ nguyên các mục đã đóng: R23 504/504, R24 development COST, Parts 1–3 trong scope Windows/archived đã kiểm, panel reconciliation, selection/model/test metrics, late ablation và posthoc CI. Các output tổng hợp được đóng gói lại, không tính lại.

## Entry points, đường dẫn và dependency

Entry point hỗ trợ là `run.py plan|validate|replay`; BAT gốc gọi controller bằng đường dẫn tuyệt đối theo vị trí giải nén. Child workers chạy ba source được allowlist và hash-pinned, với temp/output riêng và cấm network/subprocess trong producer. Lệnh model/grid/refit/threshold/score/download không được dispatch. Source lịch sử được giữ để reviewer xem thuật toán.

`config/default.json` chứa input paths dưới USERPROFILE và SHA của checkpoint gốc. Chỉ được override đường dẫn input qua external config; không đổi hashes/cohort/cache policy/stage set. 174 prepared-file identities, Step2B checkpoint identities và bốn frozen insurance cache-body digests được giữ ở config. Không tự chọn “latest” dataset để thay input thiếu.

`config/environments.json` yêu cầu engineering Python 3.13.9 cùng các version thực tế đã ghi nhận. Model Python 3.13.7/core pins được tách riêng; model execution bị chặn. Hai observed Windows distribution exports là metadata của môi trường được quan sát, không phải historical full lock hay bằng chứng clean installation. Cloud Python 3.12.14 dùng cho code tests và thiếu PyArrow/Polars. Không chạy dependency resolver hoặc cài package trong release.

## Execution order và provenance

1. Preflight source/config và existing interpreter; chạy synthetic comparator controls.
2. `p2-base`: original prepared snapshot → base mới; đối chiếu toàn bộ schema/keys/values với base gốc.
3. `p2-clean`: original Step2A/B checkpoint set + cache offline cũ → clean/PIT/registry mới; đối chiếu panels với references.
4. `development-features`: dùng Part2C mới chỉ sau parity PASS; nếu Part2C không được yêu cầu hoặc BLOCKED, việc dùng frozen checkpoint phải ghi rõ. Không dùng output của Part2C FAIL. Producer Part4 giữ primary calculations và chỉ bỏ các kiểm định đã đóng.

Điểm cắt provenance là có chủ ý: summary mới của Part2A có đường dẫn/thời gian mới, không thể giả mạo chữ ký parent của Step2B gốc. Vì vậy đây là checkpoint replay có so sánh định lượng, không phải một DAG mới liền mạch từ HTTP. Development output bị giới hạn theo thời gian; raw clean/PIT đầu vào vẫn phủ nhiều thời kỳ, nên không tuyên bố không có later raw row-group scan. Không đọc model/final-test score/cohort files để chạy producer.

Mỗi stage PASS cần producer hoàn tất, schema/row count/key uniqueness/key set/null/NaN/value comparison PASS và input trước/sau không đổi. Raw base/clean/PIT comparisons là exact; development float tolerance rtol=1e-9, atol=1e-10, integer/date/string vẫn exact. SHA byte khác vì serialization/order được báo riêng; không trình bày numerical parity thành byte identity.

## Bằng chứng kiểm tra thực tế

15 command records cloud ban đầu có 13 PASS, 2 BLOCKED, 0 FAIL; xem bản tổng hợp mới và correction note trong TEST_RESULTS.md. Source cuối có 122 manifest entries và 88 Python sources. Command, environment, input/output hashes và bản source đầu vào được giữ, không chỉ một nhãn PASS. Kiểm tra cloud không thay cho native Windows replay. Python audit guards cũng không phải sandbox OS cho mọi native library.

## Repository và rubric

Có canonical source Parts 1–5, completed-analysis source đã đóng, README Anh/Việt, requirements profiles, seeds/protocol, source manifests, logs và outputs tổng hợp. Không đưa raw Parquet, private bank-row predictions/OOF arrays, fitted models/cache bodies hoặc các ZIP bằng chứng lồng nhau vào repository. `.gitignore` chỉ là lớp phụ; actual payload được kiểm trước đóng gói.

`FINAL_RUBRIC_COMPLIANCE_MATRIX.csv` có 33 gates/subcriteria và trích vị trí rubric; điểm parent được lặp để chỉ trọng số, không cộng theo từng dòng và không tự chấm điểm. README ghi trực tiếp FDIC, course/starter provenance và AI assistance. Citations chi tiết phải giữ cùng report sau này. Public URL/visibility/deadline, report identity và giới hạn trang chưa được kiểm trong release này. Part 6 chưa viết.

## Phân loại giới hạn

Historical filing/revision vintages là thiếu dữ liệu lịch sử. Review fees, r=20/avoidability là giả định khoa học. CI đã xác minh là posthoc; provenance bootstrap lịch sử chưa phục hồi. Late ablation phải ghi ngày 18/11/2026 sau test lock. Các mục này không được chuyển thành code defect hoặc PASS bằng một kiểm tra khác. Event recall và COST-weighted recall phải trình bày riêng.

Source release đã có actual Windows checkpoint replay và independent returned-evidence review. Ba producer gates được đóng ngày 19/11/2026. Không yêu cầu rerun; không gọi bộ này đã clean-room tái tạo toàn bộ dự án end to end. Chi tiết mới và hashes trong FINAL_TECHNICAL_HANDOFF_VI.md và release_evidence/windows_independent_review_20261119/.


## Bổ sung sau nhận actual Windows return

56 files của ZIP return được giữ nguyên bytes. Source manifest thực thi trùng SHA 161f2df8be6175e71cfc020ba1291d35f2ac857b54befd0773d485189edba88b và actual config trùng bản đã giao. 174 prepared identities, Step2B và cache-body hashes khớp. Toàn bộ 112 non-key column comparisons báo delta/mismatch 0; key checks không duplicate/null/missing/unexpected. Ba panel SHA trùng nguyên bản; development chỉ có byte SHA khác. Đã rehash 34 exported outputs; 240 input-hash observations trước/sau nhất quán. Development dùng parent mới đã verified; không fallback.

Returned evidence được đọc và cross-check độc lập, không coi nhãn PASS tự nó là bằng chứng. Raw Parquet không được gửi hoặc trực tiếp đọc lại tại cloud. Không phát hiện code/runtime discrepancy trong scope đã kiểm; không có cơ sở yêu cầu chạy lại closed checks. Current stage metadata được cập nhật ở bản copy mới; original executed manifest/registry được lưu riêng, không backdate.

Sửa thêm một packaging defect: global *.csv ignore từng che các root matrices và nested aggregate evidence. Bản này whitelist rõ các CSV đã vetted; kiểm tra actual Git ignore rules chỉ đọc, không commit/push hoặc remote access.


### Release-QA correction record

After Windows verification, C16 source/config validation PASS. C17 actual Git-ignore checking failed because `/workspace/.git` was not a usable Git context; this was a test-harness prerequisite error, not a failed bank-data comparison. The original FAIL record and output remain intact. C18 used an empty temporary local bare Git context to read the source worktree ignore rules: all 15 visible/ignored cases PASS. No commit, remote, push or network operation occurred; temporary scaffolding was removed. C19 final metadata/source validation PASS after registering the corrected command.

There are 19 historical release-QA command records: 16 PASS, 2 cloud BLOCKED, and 1 corrected historical harness FAIL. These counts are separate from the three actual Windows producers, ten comparator controls and independent returned-evidence review. The final relevant QA checks PASS; there is no request to repeat bank-data/model checks. No historical status is rewritten to force a perfect history.
