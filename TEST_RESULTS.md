> Historical record, superseded for current execution status by `REPORT_STATUS.md` and S5 (25 November): second upstream replay, policy-only replay, four-layout storage sensitivity and both clean installs passed. Public clone and full E2E remain unverified.

> Current status: the 19 November continuous Windows run has now been reviewed. No further user rerun is requested. See REPRODUCTION_VERIFICATION_REPORT.md and REMAINING_ISSUES_CHECKLIST.md; the text below preserves earlier history.

> **Superseded for current reproducibility status:** this document preserves the earlier checkpoint-release history. The new QA discrepancy is addressed by `REPRODUCTION_VERIFICATION_REPORT.md`, `REMAINING_ISSUES_CHECKLIST.md` and the root README. Prior checkpoint PASS does not prove the new continuous chain; one new upstream-only Windows run is required.

# Kết quả kiểm tra code release và Windows return — 19/11/2026

**15 command records cloud ban đầu: 13 PASS, 2 BLOCKED, 0 FAIL; giữ nguyên lịch sử.** Đây là các lần gọi kiểm tra code/controller; không phải 15 lần tái tạo pipeline khoa học. Không fit model, tìm tham số, chọn threshold, lặp ablation, tính lại CI hoặc final-test inference.

Mỗi lệnh thực tế, interpreter/package versions, giờ chạy, input SHA trước/sau và output SHA nằm trong `release_evidence/<test_id>/EXECUTION_RECORD.json`. Bản source đầu vào đúng tại thời điểm chạy được giữ dưới `INPUT_SNAPSHOTS/<sha>.txt`. Vì code đã có sửa tiếp trong quá trình release, dùng C19 cho metadata cuối và C11–C15 cho source code không đổi; không trình bày log trước đó như thể đã chạy trên source cuối.

`EXECUTION_LOG_INDEX.csv` liệt kê nguyên lệnh thực tế. Output từng lệnh vốn ở thư mục mới bên ngoài repo được sao chép nguyên bytes vào `release_evidence/EXECUTED_OUTPUTS/`; `EVIDENCE_RELOCATION_MAP.csv` nối đường dẫn thực tế với bản đóng gói và SHA. Không sao chép lại raw datasets hay ZIP chẩn đoán phụ.

| Test thực sự đã chạy | Kết quả | Phạm vi |
|---|---|---|
| C01_PLAN | PASS | Actual executableworkflowplan,no scienceexecution |
| C02_CODE_VALIDATION | PASS | Source/resources/no-data/immutableprotocolreleasevalidation;notbank-datareplay |
| C03_UNIT_CONTRACTS | PASS | New20stdlibsafety/config/serializationcontracttests,no scienceimports |
| C04_SOURCE_RESOURCE_AUDIT | PASS | ActualsourceASTIO/fit/readwrite/resourcegraph,not--help-only |
| C05_PARQUET_COMPARISON_CONTROLS | BLOCKED | TensyntheticArrow/Polarscontrols only;BLOCKEDifdependenciesabsent,noinstall |
| C06_ACTUAL_REPLAY_CLOUD_PREFLIGHT | BLOCKED | Actualrestrictedworkflow invocation;expectedBLOCKEDoncloud,notproducerreplayPASS |
| C07_FAILURE_EXPORT_NEGATIVE_CONTROL | PASS | Puremockedsource-drift/no-environmentcase mustexportFAILZIP,not realproducerfailure |
| C08_CONTROLLER_SMOKE | PASS | Linuxcontrollerexportflowwithmissingprofile;no nativeWindows/realdataPASS |
| C09_FINAL_RELEASE_VALIDATION | PASS | Finalallsource/resources/nodata/protocol validationaftercodefreeze |
| C10_FINAL_RESOURCE_AUDIT | PASS | Finalsource/dataflow/resourcecatalogueafterallcodefixes |
| C11_FINAL_FAILURE_EXPORT_CONTROLS | PASS | Two mocked source-integrity failures must preserve FAIL diagnostic export; no bank data or fitting |
| C12_FINAL_FROZEN_SOURCE_VALIDATION | PASS | Final source, syntax, protocol and no-data validation after completed-analysis source inclusion |
| C13_FINAL_FROZEN_RESOURCE_AUDIT | PASS | Final AST imports, data IO, resource catalogue and prohibited-payload scan; no science execution |
| C14_FINAL_WORKFLOW_CONTRACTS | PASS | Final 20 stdlib workflow safety/configuration/comparison contracts after dispatcher error-handling change |
| C15_FINAL_WORKFLOW_PLAN | PASS | Final executable plan validates completed-analysis source registration without executing stages |

## Kết quả cuối trên cloud

- C12: 122 source/config/resource entries khớp SHA; syntax và frozen protocol hợp lệ; không có payload dữ liệu/model bị cấm.
- C13: 88 tệp Python được đọc AST, trong đó 61 tệp science source thuộc Parts 1–5. Các source còn lại là workflow, tests và completed-analysis traceability. Không thiếu literal sibling `.py`/`.sha256` bắt buộc được kiểm tra; không có lỗi được phát hiện trong phạm vi static audit.
- C14: 20 contract tests PASS, gồm stage allowlist, config bất biến, output overlap, guard network/write/model reads và scalar null/NaN/infinity comparisons. Không import scientific stack hoặc tính metric ngân hàng.
- C11: 2 fault-injection tests PASS. Mô phỏng source drift/mất manifest phải xuất FAIL diagnostic ZIP; đây là kiểm tra hành vi thất bại, không phải FAIL của dữ liệu thật.
- C08: controller smoke trên Linux xuất đúng ZIP với trạng thái BLOCKED khi thiếu input/môi trường. Đây không phải bằng chứng Windows UI/BAT hoặc native producers đã chạy thành công.
- C05: bộ 10 synthetic Arrow/Polars comparison controls BLOCKED do cloud thiếu PyArrow/Polars; không cài bổ sung. Bộ này sẽ tự chạy dưới đúng engineering interpreter trên Windows trước khi chạm producer dữ liệu.
- C06: gọi replay thực tế trên cloud dừng BLOCKED do không có engineering interpreter Windows/verified inputs; **0 producer được chạy**, không được tính là real-data replay PASS.

## Kết quả Windows mới đã kiểm độc lập

Ngày 19/11/2026, ba producer thực sự chạy trong engineering Python 3.13.9 và đúng pins. Base 1.682.616, clean 1.669.802, PIT 1.629.398, development 1.231.631 dòng. 112 cột ngoài khóa có 0 null/NaN/value mismatch, max delta 0. Base/clean/PIT SHA trùng gốc; development SHA khác nhưng schema/key/value parity khớp. Development tiêu thụ đúng parent Part2C mới sau PASS, không fallback.

10 Arrow/Polars synthetic controls đã thực thi trên Windows và kiểm tra độc lập các expected-positive/expected-negative outcomes. Vì vậy C05/C06 vẫn BLOCKED với môi trường cloud tại thời điểm cũ, còn các gates tương ứng đã có actual Windows execution mới. Không đổi status lịch sử.

`release_evidence/windows_return_20261119/` giữ nguyên 56 files trong ZIP trả về. `windows_independent_review_20261119/INDEPENDENT_REVIEW.json` ghi actual audit command, environment, hashes trước/sau và các consistency checks. Đã kiểm 240 input-hash observations (237 unique identities), rehash 34 exported files có digests, kiểm prepared174/Step2B/cache frozen hashes và CSV so với toàn bộ JSON từng cột. Không đọc lại raw Parquet ở cloud. Các expected synthetic FAIL là controls được từ chối đúng, không phải FAIL của bank datasets.

## So sánh prior và hiện tại

`PRIOR_NUMERICAL_COMPARISON.csv` giữ 9 so sánh Part3/1.089 aggregate rows đã đóng, không tính lại. `NEW_PRODUCER_REPLAY_STATUS.csv`, `WINDOWS_REPLAY_DATASET_COMPARISON.csv` và `WINDOWS_REPLAY_COLUMN_COMPARISON.csv` đã cập nhật bằng kết quả Windows thật. Không còn gate yêu cầu bạn chạy lại ba producers. Full clean-room E2E vẫn NOT EXECUTED.

Các metadata-validation/publication-ignore checks của bản đóng gói cập nhật được ghi riêng trong `EXECUTION_LOG_INDEX.csv`; không phải rerun khoa học.


### Release-QA correction record

After Windows verification, C16 source/config validation PASS. C17 actual Git-ignore checking failed because `/workspace/.git` was not a usable Git context; this was a test-harness prerequisite error, not a failed bank-data comparison. The original FAIL record and output remain intact. C18 used an empty temporary local bare Git context to read the source worktree ignore rules: all 15 visible/ignored cases PASS. No commit, remote, push or network operation occurred; temporary scaffolding was removed. C19 final metadata/source validation PASS after registering the corrected command.

There are 19 historical release-QA command records: 16 PASS, 2 cloud BLOCKED, and 1 corrected historical harness FAIL. These counts are separate from the three actual Windows producers, ten comparator controls and independent returned-evidence review. The final relevant QA checks PASS; there is no request to repeat bank-data/model checks. No historical status is rewritten to force a perfect history.
