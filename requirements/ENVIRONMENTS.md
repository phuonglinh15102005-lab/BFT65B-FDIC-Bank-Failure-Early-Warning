# Environments and pin provenance

Không có package nào được cài trong đợt repair.

| Profile | Python / runtime | Pin source | Tình trạng |
|---|---|---|---|
| Audit/repair | Python3.12.14 | `audit-tested.txt`, actual package metadata | Imports, CLI, synthetic tests đã chạy; không bảo đảm reinstall trên Windows trước khi thử resolver. |
| Engineering historical | Python3.13.9, Java17 (original Windows record) | `engineering-recorded.txt`, copied original recorded requirements | Polars/PyArrow/PySpark/requests không có ở phiên này; chưa chạy real pipeline. |
| Frozen model historical | Python3.13.7 | `model-recorded-partial.txt`, scorer's exact version gates | Chỉ biết sklearn1.9.0/numpy2.3.3/pandas2.3.3/joblib1.5.2. Cần original full environment để pin SciPy/PyArrow/transitives. |

Audit environment sklearn1.8.0/numpy2.3.5/pandas2.2.3/joblib1.5.3 không phải frozen scorer environment. Không nới lỏng version gates, không đổi fitted preprocessing và không load model để ép chạy. Part4 historical docstring còn nhắc sklearn1.9.1; cần version provenance cho stage đó, không trộn với scorer1.9.0.

Root requirements chỉ phục vụ kiểm thử local không fitting. Engineering pins là bản ghi lịch sử; model pins là partial record, không được quảng bá như fully resolved lock. Khả năng cài lại, wheel availability và dependency resolver trên Python/Windows đích chưa được kiểm chứng. Thiếu full historical lock là evidence gap còn lại, không được điền bằng version phỏng đoán.

Requests chỉ cần cho network acquisition, được import lazily; CLI/help/local metadata checks không cần requests. PyArrow cần cho Parquet I/O thật. Synthetic tests inject a dataframe reader where necessary; chúng không chứng minh Parquet serialization dưới engine chưa cài.
