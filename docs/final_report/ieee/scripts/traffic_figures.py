import pandas as pd, numpy as np, json, sys
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
SP,OUT,R=sys.argv[1],sys.argv[2],"/Users/ishanmehta/Desktop/Projects/Geospatial_MMI"
plt.rcParams.update({"font.family":"serif","font.serif":["Times New Roman","Nimbus Roman","DejaVu Serif"],"font.size":8,
 "axes.spines.top":False,"axes.spines.right":False,"axes.edgecolor":"#555","axes.linewidth":0.6,
 "xtick.major.width":0.6,"ytick.major.width":0.6,"legend.frameon":False})
BLUE,ORANGE,GREY="#2a78d6","#eb6834","#9a9a9a"
d=pd.read_csv(f"{SP}/readings.csv")
slots=list(range(0,24,2)); lab=[f"{s:02d}" for s in slots]
fig,ax=plt.subplots(1,2,figsize=(3.5,1.75))
for wk,c,mk in (("weekday",BLUE,"o"),("weekend",ORANGE,"s")):
    v=d[d.wk==wk].groupby('slot').idx.median().reindex(slots)
    ax[0].plot(slots,v.values,color=c,marker=mk,ms=2.6,lw=1.1,label=wk.capitalize()+"s")
ax[0].axhline(1,color=GREY,lw=0.6,ls=":")
ax[0].set_title("(a) Travel time / leg median",fontsize=8)
ax[0].legend(fontsize=7,loc="upper left",handlelength=1.5)
v=d.groupby('slot').ls.median().reindex(slots)
ax[1].plot(slots,v.values,color="#333",marker="o",ms=2.6,lw=1.1)
ax[1].axhline(1,color=GREY,lw=0.6,ls=":")
ax[1].set_title("(b) Travel time / static duration",fontsize=8)
for a in ax:
    a.set_xticks([0,6,12,18,22]); a.set_xticklabels(["00","06","12","18","22"]); a.set_xlabel("Time of day (IST)")
    a.set_ylim(0.6,1.4); a.grid(axis="y",color="#e4e3df",lw=0.5)
fig.tight_layout(pad=0.3,w_pad=0.8); fig.savefig(f"{OUT}/fig_traffic_by_hour.pdf"); plt.close(fig)

# map of legs
gj=json.load(open(f"{R}/data/benchmark_v2/hotspot_legs.geojson"))
fig,ax=plt.subplots(figsize=(3.5,3.0))
for hot in (False,True):
    for ft in gj["features"]:
        if bool(ft["properties"]["is_hotspot"])!=hot: continue
        xs,ys=zip(*ft["geometry"]["coordinates"])
        ax.plot(xs,ys,color=("#c0392b" if hot else "#b5b5b5"),lw=(0.9 if hot else 0.5),solid_capstyle="round")
ax.set_aspect(1/np.cos(np.radians(12.97))); ax.set_xticks([]); ax.set_yticks([])
for s in ax.spines.values(): s.set_visible(False)
ax.plot([],[],color="#b5b5b5",lw=1,label="Road legs"); ax.plot([],[],color="#c0392b",lw=1.4,label="Variable legs")
ax.legend(loc="lower left",fontsize=7)
fig.tight_layout(pad=0.1); fig.savefig(f"{OUT}/fig_legs_map.pdf"); plt.close(fig)
print("hot",sum(f["properties"]["is_hotspot"] for f in gj["features"]),"legs",len(gj["features"]))

# animation frames: Church Road, Thu 2 Apr
col={"NORMAL":"#2e9e5b","SLOW":"#f0a020","TRAFFIC_JAM":"#c0392b"}
times=[("035216","03:52"),("075216","07:52"),("135216","13:52"),("175216","17:52")]
fig,axs=plt.subplots(1,4,figsize=(3.5,1.55))
for a,(fn,t) in zip(axs,times):
    data=json.load(open(f"{R}/data/raw/gmaps_data/bangalore_routes_response_20260402_{fn}.json"))
    e=[x for x in data if x.get("road_name")=="Church Road"][0]
    for leg in e["api_response"]["routes"][0]["legs"]:
        c=leg["polyline"]["geoJsonLinestring"]["coordinates"]
        ints=leg.get("travelAdvisory",{}).get("speedReadingIntervals",[]) or [{"startPolylinePointIndex":0,"endPolylinePointIndex":len(c)-1,"speed":"NORMAL"}]
        for iv in ints:
            seg=c[iv.get("startPolylinePointIndex",0):iv.get("endPolylinePointIndex",0)+1]
            if len(seg)<2: continue
            xs,ys=zip(*seg); a.plot(xs,ys,color=col.get(iv.get("speed","NORMAL")),lw=2.2,solid_capstyle="round")
    a.set_aspect(1/np.cos(np.radians(12.97))); a.set_xticks([]); a.set_yticks([]); a.set_title(t,fontsize=8)
    for s in a.spines.values(): s.set_color("#cccccc"); s.set_linewidth(0.5); s.set_visible(True)
    a.margins(0.15)
from matplotlib.lines import Line2D
fig.legend([Line2D([],[],color=col[k],lw=2) for k in col],["Normal","Slow","Jam"],loc="lower center",ncol=3,fontsize=7,bbox_to_anchor=(0.5,-0.02))
fig.tight_layout(pad=0.2,rect=(0,0.12,1,1)); fig.savefig(f"{OUT}/fig_animation_frames.pdf"); plt.close(fig)
print("done")
