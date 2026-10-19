"""Extract only decorative artwork from the user-approved reference.
No cards, table cells, counters, control backgrounds or dynamic labels are used.
The static illustrated banner includes its branding; it replaces the older banner.
"""
from pathlib import Path
import cv2,numpy as np,json
ref=cv2.imread('docs/design/avatools-3x-target.png')
out=Path('ui/assets/approved');out.mkdir(exist_ok=True)
cv2.imwrite(str(out/'banner.png'),ref[43:191,:])
boxes={
 'metric_cast':(47,339,91,382),'metric_bite':(298,339,342,382),'metric_miss':(46,406,85,446),'overview_cart_orange':(298,408,340,446),
 'overview_bug_gray':(47,478,86,523),'overview_boat_teal':(299,482,338,521),
 'section_overview_stats':(31,289,63,319),'section_table_fish':(574,289,609,323),'section_log_document':(1143,289,1174,323),'section_tickets':(31,580,63,607),
 'ticket_ca_ro':(42,632,92,674),'ticket_ca_map':(296,631,346,674),'ticket_ca_noc':(42,730,92,773),'ticket_dock':(296,732,346,775),
 'panel_settings_gear':(102,211,135,246),'tab_target':(383,210,418,246),'button_folder':(679,213,713,245),
 'fish_ca_ro':(589,401,627,435),'fish_ca_long_tong':(589,462,627,494),'fish_cua':(589,521,627,557),
 'clock':(314,921,355,963),'button_play':(99,856,128,889),'button_pause':(355,854,392,892),'button_stop':(102,926,133,958),
}
for name,(x1,y1,x2,y2) in boxes.items():
 crop=ref[y1:y2,x1:x2].astype(float)
 # Estimate the pale, gently varying background from the crop's perimeter.
 edges=np.concatenate((crop[0],crop[-1],crop[:,0],crop[:,-1]))
 bright=edges[edges.mean(axis=1)>175]
 bg=np.median(bright if len(bright) else edges,axis=0)
 distance=np.sqrt(((crop-bg)**2).sum(axis=2))
 alpha=np.clip((distance-12)/24,0,1)
 rgb=np.clip((crop-(1-alpha[...,None])*bg)/np.maximum(alpha[...,None],.001),0,255)
 rgba=np.dstack((rgb.astype('uint8'),(alpha*255).astype('uint8')))
 cv2.imwrite(str(out/(name+'.png')),rgba)
for name in ('button_play','button_pause','button_stop','clock'):
 path=out/(name+'.png');icon=cv2.imread(str(path),-1)
 yy,xx=np.where(icon[:,:,3]>48)
 if len(xx):
  icon=icon[max(0,yy.min()-1):min(icon.shape[0],yy.max()+2),max(0,xx.min()-1):min(icon.shape[1],xx.max()+2)]
  cv2.imwrite(str(path),icon)
for name in ('button_play','button_pause','button_stop'):
 icon=cv2.imread(str(out/(name+'.png')),-1)
 icon[:,:,3]=(icon[:,:,3]*.45).astype('uint8')
 cv2.imwrite(str(out/(name+'_disabled.png')),icon)
(out/'PROVENANCE.json').write_text(json.dumps(dict(source='docs/design/avatools-3x-target.png',banner=[0,43,1534,191],decorative_icon_rectangles=boxes,method='Perimeter-background alpha extraction; no interactive widgets or dynamic text extracted.'),indent=2))
