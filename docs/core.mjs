export const fold=value=>String(value??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/đ/g,'d').toLowerCase();
export function ageDays(value,now=new Date()) {const date=Date.parse(value+'T00:00:00Z');const age=Math.floor((Date.UTC(now.getFullYear(),now.getMonth(),now.getDate())-date)/86400000);return Number.isFinite(age)&&age>=0?age:null;}
export function score(row,now=new Date()){const age=ageDays(row.lastSeen,now);return age===null?0:Math.round(Math.max(0,Math.min(row.suspect?50:100,Number(row.baseScore)||0))*2**(-Math.max(0,age-14)/45));}
export function filterRows(rows,f,now=new Date()) {return rows.filter(r=>{
 if(f.search&&!fold([r.title,r.district,r.position].join(' ')).includes(fold(f.search).trim()))return false;
 if(f.district&&r.district!==f.district)return false;
 if(f.min!==''&&r.price<Number(f.min))return false;if(f.max!==''&&r.price>Number(f.max))return false;
 if(f.beds==='studio'&&r.beds!==0)return false;if(!['any','studio'].includes(f.beds)&&(r.beds==null||r.beds<Number(f.beds)))return false;
 if(f.fresh!=='any'){const age=ageDays(r.lastSeen,now);if(age===null||age>Number(f.fresh))return false;}
 if(f.quota!=='any'&&r.mode==='buy'&&r.ownership!==f.quota)return false;
 if(f.photo&&!r.image)return false;if(f.watchlist&&!r.watchlist)return false;return true;
 }).sort((a,b)=>f.sort==='price-low'?a.price-b.price:f.sort==='price-high'?b.price-a.price:f.sort==='area'?(b.area||0)-(a.area||0):f.sort==='newest'?(b.lastSeen||'').localeCompare(a.lastSeen||''):score(b,now)-score(a,now)||(b.lastSeen||'').localeCompare(a.lastSeen||''));}
export function csvCell(value){let s=String(value??'');if(/^[=+@\-\t\r]/.test(s))s="'"+s;return '"'+s.replaceAll('"','""')+'"';}
export const safeUrl=value=>{try{const u=new URL(value);return ['https:','http:'].includes(u.protocol)&&!u.username&&!u.password?u.href:'';}catch{return '';}};
