import pandas as pd, numpy as np
# Offline re-analysis of the April traffic data for Section IV of the report. Reads output/ only; writes legs.csv and readings.csv to OUTDIR.
import sys; OUTDIR = sys.argv[1] if len(sys.argv) > 1 else "."
R="/Users/ishanmehta/Desktop/Projects/Geospatial_MMI"
f=pd.read_csv(f"{R}/output/flattened_traffic_data.csv"); m=pd.read_csv(f"{R}/output/master_subroutes.csv")
def hav(a,b,c,d):
    a,b,c,d=map(np.radians,(a,b,c,d)); x=np.sin((c-a)/2)**2+np.cos(a)*np.cos(c)*np.sin((d-b)/2)**2; return 2*6371000*np.arcsin(np.sqrt(x))
m['straight']=hav(m.start_lat,m.start_lng,m.end_lat,m.end_lng)
n=f.groupby('sub_route_id').size(); m['n']=m.sub_route_id.map(n)
inb=m.start_lat.between(12.8,13.25)&m.end_lat.between(12.8,13.25)&m.start_lng.between(77.4,77.85)&m.end_lng.between(77.4,77.85)
det=m.distance_meters<=2*m.straight
ok=inb&det&(m.n>=40)
print('legs',len(m),'outside city',(~inb).sum(),'detour>2 (in city)',(inb&~det).sum(),'few snaps (rest)',(inb&det&(m.n<40)).sum(),'kept',ok.sum())
print('removed legs >50km',(m.distance_meters>50000).sum(), 'kept max km',m[ok].distance_meters.max()/1000, 'kept median km',m[ok].distance_meters.median()/1000)
keep=set(m[ok].sub_route_id)
d=f[f.sub_route_id.isin(keep)].copy()
ts=pd.to_datetime(d.timestamp,utc=True,format='ISO8601').dt.tz_convert('Asia/Kolkata')
d['hour']=ts.dt.hour; d['dow']=ts.dt.dayofweek; d['date']=ts.dt.date
# slot = 2-hour run, label by rounded hour of run (runs at :52 -> next even hour)
d['slot']=((ts.dt.hour*60+ts.dt.minute+30)//120*2)%24
d=d.merge(m[['sub_route_id','distance_meters','straight']],on='sub_route_id')
d['idx']=d.live_duration_s/d.groupby('sub_route_id').live_duration_s.transform('median')
d['kmh']=d.distance_meters/d.live_duration_s*3.6
d['ls']=d.live_duration_s/d.static_duration_s
d['wk']=np.where(d.dow>=5,'weekend','weekday')
print(d.groupby(['wk','slot']).idx.median().unstack(0).round(3).T.to_string())
print('live/static by slot', d.groupby('slot').ls.median().round(2).to_dict())
print('share readings below static',(d.ls<1).mean().round(3),'share equal',(d.ls==1).mean().round(3))
print('speed by slot weekday', d[d.wk=='weekday'].groupby('slot').kmh.median().round(1).to_dict())
print('overall median speed',d.kmh.median().round(1))
# per-leg stats
g=d.groupby('sub_route_id')
L=pd.DataFrame({'road':g.road_name.first(),'km':g.distance_meters.first()/1000,'kmh':g.kmh.median(),
  'cv':g.live_duration_s.std()/g.live_duration_s.mean()})
hm=d.groupby(['sub_route_id','slot']).live_duration_s.median().unstack()
L['swing']=hm.max(1)/hm.min(1)
# residual: deviation from leg's slot median
d['slotmed']=d.groupby(['sub_route_id','slot']).live_duration_s.transform('median')
d['res']=np.log(d.live_duration_s/d.slotmed)
L['resid']=d.groupby('sub_route_id').res.std()
tot=d.assign(l=np.log(d.live_duration_s)).groupby('sub_route_id').l.var()
L['daily_share']=1-(d.groupby('sub_route_id').res.var()/tot)
print('legs',len(L),'median speed',L.kmh.median().round(1),'IQR',L.kmh.quantile([.25,.75]).round(1).tolist())
print('median CV',L.cv.median().round(3),'median swing',L.swing.median().round(2),'median daily share',L.daily_share.median().round(2),'median resid',L.resid.median().round(3))
print('spearman swing vs resid',round(L.swing.rank().corr(L.resid.rank()),3),' cv vs daily share', round(L.cv.rank().corr(L.daily_share.rank()),3))
q=L.swing.quantile(.75); print('top25 swing resid',L[L.swing>=q].resid.median().round(3),'rest',L[L.swing<q].resid.median().round(3))
top=L.cv.quantile(.8); print('hotspot cut cv',round(top,3),'n hot',(L.cv>=top).sum())
print(L.sort_values('kmh').head(6).round(2).to_string())
print(L[L.km>=1].sort_values('kmh').head(6).round(2).to_string())
print(L.sort_values('swing',ascending=False).head(6).round(2).to_string())
L.to_csv(fOUTDIR + "/legs.csv")
d[['sub_route_id','slot','wk','idx','ls','kmh']].to_csv(fOUTDIR + "/readings.csv",index=False)
print('distinct slots',sorted(d.slot.unique()), 'days per wk', d.groupby('wk').date.nunique().to_dict())
