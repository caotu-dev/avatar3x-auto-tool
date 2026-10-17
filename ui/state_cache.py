"""Durable per-device observations; unknown fields never become known by default."""
import json
from datetime import date

def load(path, serial):
    try:
        if not path.exists():
            old=json.loads((path.parent/'ui_last.json').read_text(encoding='utf-8'))
            if not isinstance(old,dict):return {}
            saved={'version':1,'serial':serial,'inventory':old,
                   'quest':{'targets':old.get('targets',[]),'title':old.get('quest_title')}}
        else:
            saved=json.loads(path.read_text(encoding='utf-8'))
        if saved.get('version')!=1 or saved.get('serial')!=serial:
            return {}
        data=saved['inventory']; result={}
        tickets={}
        for key in ('ca_ro','ca_noc','ca_map','dock'):
            value=data.get('tickets',{}).get(key,{})
            if value.get('status') not in ('active','missing','unknown'):continue
            expiry=value.get('expires_on')
            if expiry is not None:
                if date.fromisoformat(expiry)<date.today():
                    value={'status':'unknown','expires_on':None}
            tickets[key]=value
        result['tickets']=tickets
        result['bait_stocks']={k:v for k,v in data.get('bait_stocks',{}).items()
                               if k in ('ecological','dock') and (v is None or type(v) is int and v>=0)}
        result['bait_remaining']=result['bait_stocks'].get('ecological')
        for key in ('scan_complete','inventory_observed_at','inventory_updated_at','bait_estimated','wallet'):
            if key in data:result[key]=data[key]
        result['quest']=saved.get('quest')
        return result
    except (OSError,ValueError,TypeError,KeyError,AttributeError):
        return {}

def save(path, serial, data, mission):
    previous=load(path,serial)
    quest=previous.get('quest')
    if mission and data.get('targets') and data.get('quest_title'):
        quest={'targets':data['targets'],'title':data.get('quest_title')}
    payload={'version':1,'serial':serial,'quest':quest,'inventory':{k:data[k] for k in
             ('tickets','bait_stocks','bait_estimated','wallet','scan_complete','inventory_observed_at','inventory_updated_at') if k in data}}
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    temporary.replace(path)
