"""Build an audit summary from saved observations; never sends game inputs."""
import json,sys
from pathlib import Path
from collections import Counter
import cv2
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from fishing.catch import CatchDetector,SPECIES
project=Path(__file__).resolve().parents[3]
root=project/'debug/live-inventory-dock'
ledger=json.loads((root/'bounded-ledger.json').read_text(encoding='utf-8'))
records=[]
for folder in [root/'trial-first',root/'trial-second',*sorted(root.glob('bounded-*'))]:
 if not folder.is_dir():continue
 for result in sorted(folder.glob('round_*/result.json')):
  record=json.loads(result.read_text(encoding='utf-8'));record['folder']=str(result.parent.relative_to(project))
  if record['outcome']=='SUCCESS':
   screen=next(result.parent.glob('*_STOP.png'))
   fish=CatchDetector(area='dock').detect(cv2.imread(str(screen)))
   record.update(fish_species=fish.species,fish_name=fish.name,fish_confidence=fish.confidence)
   record['recognition']='Reclassified from preserved result image using live-trained templates'
  records.append(record)
counts=Counter(r['outcome'] for r in records)
fish=Counter(r['fish_species'] or 'unknown' for r in records if r['outcome']=='SUCCESS')
assert sum(r['casts'] for r in records)<=ledger['casts']<=100
report={'status':ledger.get('status','RUNNING'),'cast_limit':100,'attempts':ledger['casts'],
 'completed_results':len(records),'outcomes':dict(counts),'fish_counts':dict(fish),
 'catalog':{s:SPECIES[s] for s in fish if s in SPECIES},'bait_purchases':ledger['purchases'],
 'bait_purchased':ledger['purchased'],'stock_estimate':ledger['remaining'],
 'initial_wallet':{'coins':1614861,'gold':264},'records':records}
for folder,key in [('post-buy1','after_first_purchase'),('dock-buy2','after_second_purchase'),('final-chest','final_inventory'),('perch-ticket','after_ticket_test')]:
 path=root/folder/('inventory.json' if folder=='dock-buy2' else 'result.json')
 if path.exists():report[key]=json.loads(path.read_text(encoding='utf-8'))
out=Path(__file__).parent/'validation/live-results.json'
out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:report[k] for k in ('status','attempts','completed_results','outcomes','fish_counts','bait_purchases')},ensure_ascii=True))
