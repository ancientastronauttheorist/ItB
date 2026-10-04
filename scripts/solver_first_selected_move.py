"""Acquire the offline conditional selected Move producer receipt."""
import argparse
import faulthandler
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'.local_decompile/fill_runtime'))
from src.observatory.solver_first_selected_move import run

def main():
 faulthandler.disable();p=argparse.ArgumentParser(__doc__);p.add_argument('--exe',type=Path,required=True);p.add_argument('--private-dir',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
 if a.report.exists():p.error('report path is create-only')
 report=run(a.exe,a.private_dir)
 with a.report.open('x',encoding='utf-8',newline='\n') as f:json.dump(report,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n')
 print(json.dumps({k:report[k] for k in ('status','failure','attempted','admitted','failed','original_call_count','instruction_count','private_receipt_sha256')},indent=2))
 return int(report['failed']!=0)
if __name__=='__main__':raise SystemExit(main())
