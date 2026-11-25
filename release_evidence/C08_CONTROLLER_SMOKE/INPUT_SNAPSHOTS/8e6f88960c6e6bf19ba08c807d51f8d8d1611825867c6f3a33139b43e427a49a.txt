"""Linux controller smoke with deliberately unavailable Windows inputs, no raw replay."""
from pathlib import Path
import json,os,subprocess,sys,zipfile
ROOT=Path(__file__).resolve().parents[1]
BASE=Path('/workspace/work/BFT65B_FINAL_CODE_CONTROLLER_SMOKE_20261118')
def main():
    if BASE.exists():raise ValueError('Smoke output already exists;preserve previous evidence')
    child=subprocess.run([sys.executable,'-B',str(ROOT/'workflow/windows_start.py')],capture_output=True,text=True,
                         env={**os.environ,'USERPROFILE':'/workspace/NO_WINDOWS_INPUT_PROFILE','LOCALAPPDATA':str(BASE),'PYTHONDONTWRITEBYTECODE':'1','PYTHONUTF8':'1'})
    archives=list(BASE.rglob('*_GUI_LAI_CHO_CODEX.zip'))
    assert child.returncode==0 and len(archives)==1
    with zipfile.ZipFile(archives[0]) as archive:
        assert archive.testzip() is None
        result=json.loads(archive.read('REPLAY_RESULT.json'))
        assert result['status']=='BLOCKED' and result['new_model_fits']==0 and result['full_clean_room_E2E']=='NOT_EXECUTED'
        assert all(x['status']=='BLOCKED' for x in result['stages'].values())
        assert not any(name.endswith(('.parquet','.npz','.joblib','.pkl')) for name in archive.namelist())
        assert 'STAGE_STATUS.csv' in archive.namelist()
    status={'status':'PASS_CONTROLLER_BLOCKED_EXPORT_FLOW_ONLY','platform_scope':'Linux,not native Windows',
            'actual_producer_execution':'BLOCKED','new_model_fits':0,'controller_command':[sys.executable,'-B',str(ROOT/'workflow/windows_start.py')],
            'stdout':child.stdout,'stderr':child.stderr,'exported_zip':str(archives[0])}
    target=BASE/'CONTROLLER_SMOKE_RESULT.json';target.write_text(json.dumps(status,indent=2))
    print(json.dumps({k:status[k] for k in ['status','platform_scope','actual_producer_execution','new_model_fits']},indent=2))
if __name__=='__main__':main()
