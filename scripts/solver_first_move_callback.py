"""Acquire conditional original stock Move target/effect callbacks offline."""
import argparse
import faulthandler
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable',type=Path,required=True)
    parser.add_argument('--runtime-path',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--private-output-dir',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists() or args.private_output_dir.exists():
        parser.error('outputs are create-only')
    if args.runtime_path:
        sys.path.insert(0,str(args.runtime_path.resolve()))
    faulthandler.disable()
    from src.observatory.solver_first_move_callback import run
    report=run(args.executable,args.private_output_dir)
    with args.output.open('x',encoding='utf-8',newline='\n') as handle:
        json.dump(report,handle,indent=2,sort_keys=True,allow_nan=False);handle.write('\n')
    print(json.dumps({k:report[k] for k in ('attempted','admitted','matched','failed','excluded','status','failure')}))
    return int(report['failed']!=0)


if __name__=='__main__':
    raise SystemExit(main())
