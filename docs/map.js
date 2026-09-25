// Map view for Property Scout. Leaflet + markercluster load lazily the first time the map opens.
const CDN='https://cdnjs.cloudflare.com/ajax/libs/';
const ASSETS=[['css',CDN+'leaflet/1.9.4/leaflet.min.css'],['css',CDN+'leaflet.markercluster/1.5.3/MarkerCluster.min.css'],['css',CDN+'leaflet.markercluster/1.5.3/MarkerCluster.Default.min.css'],['js',CDN+'leaflet/1.9.4/leaflet.min.js'],['js',CDN+'leaflet.markercluster/1.5.3/leaflet.markercluster.min.js']];
const CENTER={bangkok:[13.7466,100.5393],saigon:[10.7769,106.7009]};
export const PRECISION={listing:'Exact building · from the listing page',building:'Building · matched to another listing of the same building',osm:'Building name found on OpenStreetMap · check the pin',district:'Area only · not the building position'};
let ready,map,cluster,me,layerKey='',opts;
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function asset([kind,url]){return new Promise((ok,fail)=>{const el=document.createElement(kind==='css'?'link':'script');if(kind==='css'){el.rel='stylesheet';el.href=url;ok();}else{el.src=url;el.onload=ok;el.onerror=()=>fail(Error('Map library could not load'));}document.head.append(el);});}
async function loadLeaflet(){if(!ready)ready=(async()=>{for(const a of ASSETS)await asset(a);})();return ready;}
const short=(r)=>{const v=r.price;return r.mode==='rent'?'$'+Math.round(v):v>=1e6?'$'+(v/1e6).toFixed(2)+'M':'$'+Math.round(v/1000)+'k';};
function icon(r,saved){const cls=['pin',r.geo==='district'?'approx':r.geo==='osm'?'osm':'exact',saved?'saved':'',r.review?'fresh':''].join(' ');return L.divIcon({className:'',html:`<span class="${cls}">${r.geo==='district'?'~ ':''}${esc(short(r))}</span>`,iconSize:null,iconAnchor:[0,0]});}
function popup(r){const img=opts.imageUrl(r.image);return `<div class="map-pop" data-id="${r.id}">${img?`<img src="${esc(img)}" alt="" loading="lazy">`:''}<p class="mp-price">${esc(opts.money(r.price))}${r.mode==='rent'?' <small>/ month</small>':''}</p><p class="mp-title">${esc(r.title)}</p><p class="mp-meta">${esc(opts.beds(r.beds))} · ${r.area?esc(r.area)+' m²':'size n/a'} · seen ${esc(opts.date(r.lastSeen))}</p><p class="mp-geo ${r.geo}">${esc(PRECISION[r.geo]||'')}</p>${r.review?'<p class="mp-new">New in September scans · not yet reviewed</p>':''}<div class="mp-actions"><button data-map="detail">Details</button><button data-map="save" aria-pressed="${opts.isSaved(r.id)}">${opts.isSaved(r.id)?'Saved':'Save'}</button><a href="https://www.google.com/maps/search/?api=1&query=${r.lat},${r.lng}" target="_blank" rel="noopener">Street View ↗</a></div></div>`;}
export async function initMap(el,handlers){opts=handlers;await loadLeaflet();if(map)return map;
 map=L.map(el,{zoomControl:true,preferCanvas:true,maxZoom:20,worldCopyJump:false});
 const esri=(svc,attr,z=19)=>L.tileLayer(`https://server.arcgisonline.com/ArcGIS/rest/services/${svc}/MapServer/tile/{z}/{y}/{x}`,{maxZoom:20,maxNativeZoom:z,attribution:attr});
 const base={
  'Streets':esri('World_Street_Map','Tiles © Esri — Esri, HERE, Garmin, © OpenStreetMap contributors'),
  'OpenStreetMap':L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:20,maxNativeZoom:19,attribution:'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}),
  'Satellite':L.layerGroup([esri('World_Imagery','Imagery © Esri, Maxar, Earthstar Geographics'),esri('Reference/World_Boundaries_and_Places','Labels © Esri')])};
 base.Streets.addTo(map);L.control.layers(base,null,{position:'topright'}).addTo(map);L.control.scale({imperial:false}).addTo(map);
 const Locate=L.Control.extend({onAdd(){const b=L.DomUtil.create('button','map-locate');b.type='button';b.title='Show my location';b.setAttribute('aria-label','Show my location');b.textContent='◎';L.DomEvent.disableClickPropagation(b);b.onclick=()=>locate();return b;}});new Locate({position:'topleft'}).addTo(map);
 cluster=L.markerClusterGroup({chunkedLoading:true,showCoverageOnHover:false,spiderfyOnMaxZoom:true,disableClusteringAtZoom:18,maxClusterRadius:z=>z>=16?30:55});map.addLayer(cluster);
 map.on('popupopen',e=>{const box=e.popup.getElement();box.onclick=ev=>{const b=ev.target.closest('[data-map]');if(!b)return;const id=box.querySelector('[data-id]').dataset.id;if(b.dataset.map==='detail')opts.onDetail(id,b);if(b.dataset.map==='save'){opts.onSave(id);const s=opts.isSaved(id);b.textContent=s?'Saved':'Save';b.setAttribute('aria-pressed',String(s));}};});
 return map;}
function locate(){if(!navigator.geolocation){opts.feedback('Location is not available on this device.');return;}navigator.geolocation.getCurrentPosition(p=>{const ll=[p.coords.latitude,p.coords.longitude];if(me)me.remove();me=L.circleMarker(ll,{radius:8,color:'#fff',weight:3,fillColor:'#2f6fed',fillOpacity:1}).addTo(map).bindTooltip('You are here');map.setView(ll,16);},()=>opts.feedback('Location permission was not granted.'),{enableHighAccuracy:true,timeout:10000});}
export function renderMap(rows,{key,approx,focusId}={}){if(!map)return {shown:0};
 const pts=rows.filter(r=>Number.isFinite(r.lat)&&Number.isFinite(r.lng)&&(approx||r.geo!=='district'));
 cluster.clearLayers();const markers=[];let focus;
 for(const r of pts){const m=L.marker([r.lat,r.lng],{icon:icon(r,opts.isSaved(r.id)),title:r.title,riseOnHover:true,keyboard:true});m.bindPopup(()=>popup(r),{maxWidth:260,minWidth:220,autoPanPadding:[20,60]});markers.push(m);if(r.id===focusId)focus=m;}
 cluster.addLayers(markers);
 map.invalidateSize();
 if(key!==layerKey){layerKey=key;const city=key.split('-')[0];if(pts.length){const q=(a,f)=>a[Math.min(a.length-1,Math.floor(a.length*f))],la=pts.map(r=>r.lat).sort((a,b)=>a-b),ln=pts.map(r=>r.lng).sort((a,b)=>a-b),trim=pts.length>40?0.02:0;map.fitBounds([[q(la,trim),q(ln,trim)],[q(la,1-trim),q(ln,1-trim)]],{maxZoom:15,padding:[10,10]});}else map.setView(CENTER[city]||CENTER.bangkok,12);}
 if(focus)cluster.zoomToShowLayer(focus,()=>{map.setView(focus.getLatLng(),Math.max(map.getZoom(),18));focus.openPopup();});
 setTimeout(()=>map.invalidateSize(),0);
 return {shown:pts.length,total:rows.length,approx:rows.filter(r=>r.geo==='district').length};}
export function mapReady(){return !!map;}
