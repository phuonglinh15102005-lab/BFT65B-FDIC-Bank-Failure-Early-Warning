> Historical record, superseded for current execution status by `REPORT_STATUS.md` and S5 (25 November): second upstream replay, policy-only replay, four-layout storage sensitivity and both clean installs passed. Public clone and full E2E remain unverified.

> Current status: the 19 November continuous Windows run has now been reviewed. No further user rerun is requested. See REPRODUCTION_VERIFICATION_REPORT.md and REMAINING_ISSUES_CHECKLIST.md; the text below preserves earlier history.

> **Superseded for current reproducibility status:** this document preserves the earlier checkpoint-release history. The new QA discrepancy is addressed by `REPRODUCTION_VERIFICATION_REPORT.md`, `REMAINING_ISSUES_CHECKLIST.md` and the root README. Prior checkpoint PASS does not prove the new continuous chain; one new upstream-only Windows run is required.

# BFT65B — đóng gate replay Windows ngày 19/11/2026

Đã kiểm tra độc lập ZIP `20261119_082051_38aac2a6_GUI_LAI_CHO_CODEX.zip` (SHA-256 `30e4f95b91392916076e48bfa25795582af64bc95ff09ae870ceeefa751ac2a2`). Ba producer còn thiếu replay đã hoàn tất trong đúng engineering environment. Không cần chạy lại bộ BAT hoặc các kiểm định khoa học đã đóng.

| Dataset mới | Số dòng | So với reference |
|---|---:|---|
| Base panel | 1.682.616 | SHA byte trùng; schema/keys/values khớp. |
| Clean panel | 1.669.802 | SHA byte trùng; schema/keys/values khớp. |
| PIT panel | 1.629.398 | SHA byte trùng; schema/keys/values khớp. |
| Development features/cohort | 1.231.631 | Schema 20 cột và giá trị theo keys khớp; SHA byte khác. |

Có 112 cột ngoài khóa được so sánh; tất cả báo 0 mismatch null/NaN/giá trị và max absolute delta 0. Tolerance tài chính của development là rtol=1e-9, atol=1e-10, nhưng sai khác quan sát thực tế bằng 0. Không suy đoán nguyên nhân SHA khác chỉ từ logs; không gọi hai tệp development byte-identical.

10 synthetic comparator controls cũng được thực thi thành công trên Windows: các trường hợp sai dữ liệu có chủ ý bị comparator từ chối đúng. 240 hash observations của 237 input identities nhất quán trước/sau; đã tính lại SHA cho 34 exported output files có digest trong stage manifests. 174 prepared snapshot identities, các Step2B và cache-body digests khớp cấu hình đã giao. Phần raw Parquet ở máy Windows không được gửi lên cloud hoặc hash lại trực tiếp tại đây.

Commands và source hashes khớp bản release đã giao. Không có source drift được báo. Development dùng clean/PIT/registry mới của Part2C sau parity PASS, không dùng fallback. Logs/commands phù hợp với 0 new model fits, không final-test inference và không lặp R23/R24/ablation/model metrics. Đây là kiểm tra log và code provenance, không phải OS-level attestation cho mọi hoạt động trên máy.

**Đã đóng ba checkpoint-replay gates. Full clean-room E2E vẫn NOT EXECUTED.** Part2C tiếp tục dựa vào original Step2A/B signatures; chưa tái chạy acquisition, toàn bộ search/refit hay one-time test trong clean environment. Bộ này có thể giao independent final technical review, không thể gọi là toàn bộ project đã clean-room reproduced.

Các giới hạn phải giữ: historical filing/revision vintages; assumptions về review fees/r=20/avoidability; historical bootstrap provenance khác posthoc CI đã kiểm; ngày ablation muộn 18/11/2026; event recall khác COST-weighted recall. Public GitHub URL/visibility/deadline, report citations/identity và appendix page limit vẫn thuộc bước nộp bài riêng. Không sửa report hoặc viết Part 6 trong đợt này.
