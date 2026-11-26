"""Verify the archived aggregate S7 diagnostic; does not read Parquet or fit models."""
from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parent
EXPECTED='791158d72ff0b8b99b538a74a60381a2c5510f4e5d53b58cc29b7c1feafd6e00'
EXPECTED_SCRIPT='b0b8e638007146cad15be8f9f9ac23f187117270d8ac97c3110e5fe18dd83c27'
def require(ok,msg):
    if not ok: raise RuntimeError(msg)
def main():
    p=R/'S7_DIAGNOSTIC.json'; require(hashlib.sha256(p.read_bytes()).hexdigest()==EXPECTED,'S7 archive hash mismatch')
    require(hashlib.sha256((R/'BFT65B_PARQUET_SHA_DIAG.py').read_bytes()).hexdigest()==EXPECTED_SCRIPT,'S7 diagnostic script hash mismatch')
    j=json.loads(p.read_text(encoding='utf-8'))
    require(j['original_sha256']=='d365ce25204a3dcace715db4cea259c94b1b1abba4822c7bcf2b050a1c7f6a73','wrong original')
    require(j['replay_sha256']=='a7295637cc68f91bc02aa8c78e8d952b12abffda30fbb420e3c8a0d0d2662b61','wrong replay')
    require(j['rows']==1231631 and j['keys']==['CERT','DECISION_DATE'],'wrong cohort')
    require(all(j[k] is True for k in ['key_set_equal','unique_keys','schema_equal_excluding_metadata','arrow_schema_metadata_equal','inputs_preserved']) and j['key_order_equal'] is False,'key/schema/preservation result changed')
    cols=['SOURCE_REPDTE','SPLIT','log_assets','equity_to_assets','negative_equity_flag','asset_log_growth_1q','asset_log_growth_4q','nclnls_to_loans','loan_allowance_to_loans','cash_to_assets','cash_and_securities_to_assets','deposits_to_assets','net_loans_to_assets','roa_reported_percent','nimy_reported_percent','loss_flag_roa_negative','loan_denominator_invalid_flag','Y_4Q']
    require([x['column'] for x in j['columns']]==cols,'column mismatch')
    require(all(x[k]==0 for x in j['columns'] for k in ['null_mismatches','numeric_exact_mismatches','float_bit_mismatches','nan_mask_mismatches']),'nonzero mismatch')
    require(j['value_or_null_mismatches']==j['float_bit_mismatches']==0,'aggregate mismatch')
    require(all(x.get('max_abs_finite_difference',0)==0 for x in j['columns']),'nonzero finite difference')
    a,b=j['original_parquet_metadata'],j['replay_parquet_metadata']
    require(a['created_by']==b['created_by'] and a['kv_metadata_value_hashes']==b['kv_metadata_value_hashes'],'writer/schema metadata mismatch')
    require(a['row_groups']==b['row_groups']==12 and sum(a['rows_per_group'])==sum(b['rows_per_group'])==j['rows'] and a['rows_per_group']!=b['rows_per_group'],'row-group result mismatch')
    require(set(j['metadata_fields_differing'])=={'rows_per_group','footer_serialized_size','columns'} and j['conclusion']=='EXACT_DECODED_VALUES_MATCH_ROW_ORDER_DIFFERS','conclusion mismatch')
    print('PASS_S7_ARCHIVED_EXACT_COMPARISON_ONLY')
if __name__=='__main__':main()
