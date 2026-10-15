"""Generate a local immutable-image override after all release gates pass."""
import argparse,json,re
from pathlib import Path


def manifest(image):
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._:/-]+@sha256:[0-9a-f]{64}',image): raise ValueError('immutable registry image digest required')
    return {'services':{service:{'image':image,'pull_policy':'always'} for service in ('core','worker-tpr','worker-timer','simulator','volume-init','dashboard')}}


def main():
    p=argparse.ArgumentParser();p.add_argument('--image',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    with Path(a.output).open('x') as out: json.dump(manifest(a.image),out,indent=2)

if __name__=='__main__': main()
