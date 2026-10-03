// Dummy backend: ALL data here is SIMULATED (not real Maitri/Bharati telemetry).
import express from 'express';import cors from 'cors';
const app=express();app.use(cors(),express.json());
const R=(a,b)=>a+Math.random()*(b-a),cl=(v,a,b)=>Math.min(b,Math.max(a,v)),r1=v=>Math.round(v*10)/10;
const day=n=>new Date(Date.now()+n*864e5).toISOString().slice(0,10);
const settings={vibWarn:4.5,vibCrit:6,batteryWarn:30,tempWarn:-35,windWarn:22};
const audit=[];const log=(u,a)=>{audit.unshift({t:new Date().toISOString(),user:u||'system',action:a});audit.length=Math.min(audit.length,100)};
const USERS=[
 {email:'admin@ncpor.in',name:'Dr. Asha Rao',role:'admin',stations:['maitri','bharati']},
 {email:'ops@ncpor.in',name:'Vikram Nair',role:'ops',stations:['maitri','bharati']},
 {email:'maint@ncpor.in',name:'Isha Menon',role:'maintenance',stations:['bharati']},
 {email:'logistics@ncpor.in',name:'Rohan Das',role:'logistics',stations:['maitri']}];

const DEFS=[['gen1','Generator 01','generator',6,4,16,9,['bat'],30],['gen2','Generator 02','generator',6,16,16,9,['bat'],30],['gen3','Generator 03','generator',6,28,16,9,['bat'],30],
 ['fuel','Fuel Tank Farm','fuel',6,41,16,9,['gen1','gen2','gen3']],['bat','Battery Bank','battery',34,4,16,10,['heat','living','lab','comms','water']],
 ['heat','Heating Plant','heating',34,20,16,10,[]],['water','Water Plant','water',34,36,16,10,[]],['living','Living Module','living',62,4,18,12,[]],
 ['lab','Science Lab','lab',62,22,18,12,[]],['comms','Comms Hub','comms',62,40,18,10,[]]];
const mkAssets=()=>DEFS.map(([id,name,type,x,y,w,h,links,cap])=>({id,name,type,x,y,w,h,links,cap:cap||0,online:true,hours:Math.round(R(1500,9000)),last:day(-R(20,80)),next:day(R(8,60)),vib:2.2,hist:[],readings:[],status:'normal'}));
const mkInv=(fuel,spare)=>[{k:'fuel',name:'Fuel (diesel)',unit:'L',stock:fuel,cap:20000,rate:0,min:25},{k:'food',name:'Food',unit:'kg',stock:1500,cap:3000,rate:24,min:20},
 {k:'med',name:'Medical supplies',unit:'units',stock:420,cap:600,rate:4,min:25},{k:'parts',name:'Spare parts',unit:'units',stock:spare,cap:100,rate:3.2,min:30},{k:'water',name:'Water reserve',unit:'L',stock:52000,cap:90000,rate:1500,min:20}];
const mk=(id,name,o)=>({id,name,t:o.t,w:o.w,p:o.p,env:{temp:o.t,wind:o.w,dir:200,pressure:o.p,snow:o.sn,vis:9},assets:mkAssets(),baseLoad:o.base,solar:o.solar,capFactor:1,
 battery:{kwh:400,pct:o.bat},resupplyIn:o.res,inv:mkInv(o.fuel,o.spare),hist:[],cold:o.cold,acked:{},seen:{},nextTask:3,
 tasks:[{id:1,assetId:'gen2',title:'Vibration analysis & bearing inspection',status:'Open',due:day(3),parts:'Bearing kit',by:'system'},{id:2,assetId:'comms',title:'Antenna alignment check',status:'Open',due:day(9),parts:'-',by:'system'}]});
const S={maitri:mk('maitri','Maitri',{t:-14,w:9,p:985,sn:8,base:36,solar:6,bat:84,res:24,fuel:14000,spare:90,cold:false}),
 bharati:mk('bharati','Bharati',{t:-18,w:12,p:975,sn:14,base:42,solar:4,bat:63,res:20,fuel:9000,spare:38,cold:true})};

const calc=s=>{const heat=Math.max(0,-5-s.env.temp)*.9+10;const demand=s.baseLoad+heat;
 const capGen=s.assets.filter(a=>a.type==='generator'&&a.online).reduce((t,a)=>t+a.cap,0)*s.capFactor;const cap=capGen+s.solar*s.capFactor;
 const output=Math.min(demand,cap);return{heat,demand,cap,capGen,output,genOut:Math.max(0,output-s.solar*s.capFactor),deficit:Math.max(0,demand-cap)}};
const rateOf=(s,i)=>i.k==='fuel'?calc(s).genOut*.3*24:i.rate;
const daysOf=(s,i)=>{const r=rateOf(s,i);return r>0?i.stock/r:999};
const risk=(s,d)=>d<s.resupplyIn?'critical':d<s.resupplyIn+7?'warning':'ok';

function tick(s){const e=s.env;
 e.temp=cl(e.temp+(s.t-e.temp)*.03+R(-.5,.5),-48,2);e.wind=cl(e.wind+(s.w-e.wind)*.05+R(-1.2,1.2),0,40);e.dir=(e.dir+R(-6,6)+360)%360;
 e.pressure=cl(e.pressure+(s.p-e.pressure)*.02+R(-.8,.8),930,1010);e.snow=cl(e.snow+R(-.3,.5),0,60);e.vis=cl(e.vis+(9-e.vis)*.05+R(-.6,.6)-(e.wind>20?.3:0),.3,10);
 const m=calc(s),b=s.battery;
 if(m.deficit>0)b.pct-=m.deficit/6/b.kwh*100;else b.pct+=Math.min(20,m.cap-m.demand)*.5/6/b.kwh*100;b.pct=cl(b.pct,0,100);
 s.inv.forEach(i=>{i.stock=Math.max(0,i.stock-rateOf(s,i)/144)});
 const fuel=s.inv[0],fd=daysOf(s,fuel);
 for(const a of s.assets){let rd=[],st='normal';
  switch(a.type){
   case'generator':{const load=a.online&&m.capGen?cl(m.genOut,0,m.capGen)/m.capGen*100:0;a.vib=!a.online?0:a.drift?Math.min(9,a.vib+R(.03,.1)):2.2+R(-.2,.3);
    const t=a.online?62+load*.3+R(-1,1):-5;rd=[['Vibration',a.vib,'mm/s'],['Temperature',t,'°C'],['Power output',a.cap*load/100,'kW'],['Load',load,'%'],['Operating hours',a.hours,'h']];
    st=!a.online?'offline':a.vib>settings.vibCrit?'critical':(a.vib>settings.vibWarn||t>95)?'warning':'normal';break}
   case'battery':rd=[['Charge',b.pct,'%'],['Voltage',48+b.pct*.08+R(-.1,.1),'V'],['Net flow',m.deficit>0?-m.deficit:Math.min(20,m.cap-m.demand)*.5,'kW']];st=b.pct<10?'critical':b.pct<settings.batteryWarn?'warning':'normal';break;
   case'heating':rd=[['Heat output',m.heat,'kW'],['Supply temp',55+m.heat*.6,'°C']];st=m.deficit>0?'warning':'normal';break;
   case'water':{const w=s.inv[4],p=w.stock/w.cap*100;rd=[['Level',p,'%'],['Flow',R(8,12),'L/min']];st=p<w.min?'warning':'normal';break}
   case'living':rd=[['Indoor temp',21-Math.min(8,m.deficit*.3),'°C'],['Power draw',s.baseLoad*.3,'kW']];st=m.deficit>0?'warning':'normal';break;
   case'lab':rd=[['Indoor temp',20-Math.min(8,m.deficit*.3),'°C'],['Power draw',s.baseLoad*.35,'kW']];st=m.deficit>0?'warning':'normal';break;
   case'comms':{const q=cl(92-e.wind*.9+R(-2,2),0,100);rd=[['Link quality',q,'%'],['Latency',500+(100-q)*12+R(-30,30),'ms']];st=q<60?'warning':'normal';break}
   case'fuel':rd=[['Level',fuel.stock/fuel.cap*100,'%'],['Days remaining',fd,'d']];st=risk(s,fd)==='ok'?'normal':risk(s,fd);}
  a.readings=rd.map(([k,v,u])=>({k,v:r1(v),u}));a.status=st;a.hist=[...a.hist,a.readings[0].v].slice(-30)}
 s.hist=[...s.hist,{t:new Date().toLocaleTimeString('en-GB'),gen:r1(m.output),demand:r1(m.demand),cap:r1(m.cap),battery:r1(b.pct),temp:r1(e.temp),wind:r1(e.wind),pressure:r1(e.pressure),snow:r1(e.snow)}].slice(-40)}
let lastTick=Date.now();
Object.values(S).forEach(s=>{for(let i=0;i<30;i++)tick(s)});
S.bharati.assets.find(a=>a.id==='gen2').drift=true;S.bharati.assets.find(a=>a.id==='gen2').vib=3.4;
setInterval(()=>{Object.values(S).forEach(tick);lastTick=Date.now()},3000);

function alerts(s){const out=[],m=calc(s),b=s.battery;
 const add=(key,severity,title,source,assetId,link,desc,impact,action,why)=>{const id=`${s.id}:${key}`;s.seen[id]??=new Date().toISOString();out.push({id,severity,title,source,assetId,link,desc,impact,action,why,time:s.seen[id],acked:!!s.acked[id]})};
 for(const a of s.assets){if(a.status==='normal'||['battery','fuel'].includes(a.type))continue;const sev=a.status==='warning'?'warning':'critical',r0=a.readings[0];
  if(a.type==='generator'){if(!a.online)add(`${a.id}-off`,'critical','Generator offline',a.name,a.id,`/twin?asset=${a.id}`,`${a.name} is not running.`,'Reduced generation capacity; higher load on remaining units.','Check fault logs and restart or isolate the unit.','Rule: asset status = offline.');
   else add(`${a.id}-vib`,sev,'Abnormal vibration',a.name,a.id,`/twin?asset=${a.id}`,`Vibration ${r0.v} mm/s vs baseline ~2.2 mm/s.`,'Reduced reliability of power generation.','Inspect the asset and review its operating parameters.',`Rule: vibration > ${settings.vibWarn} mm/s (warning) or > ${settings.vibCrit} mm/s (critical).`)}
  else add(a.id,sev,`${a.name} needs attention`,a.name,a.id,`/twin?asset=${a.id}`,`${r0.k}: ${r0.v} ${r0.u}.`,'Possible effect on station comfort or operations.','Review the asset and linked systems.','Rule: reading outside its normal operating range or linked to an energy deficit.')}
 if(b.pct<settings.batteryWarn)add('battery',b.pct<10?'critical':'warning','Low battery reserve','Battery Bank','bat','/energy',`Battery at ${r1(b.pct)}%.`,'Less buffer for generator faults.','Reduce non-critical loads; check generation.',`Rule: battery < ${settings.batteryWarn}%.`);
 const fd=daysOf(s,s.inv[0]);if(risk(s,fd)!=='ok')add('fuel',risk(s,fd),'Fuel may not last until resupply','Logistics','fuel','/logistics',`${r1(fd)} days of fuel at current burn; resupply in ${s.resupplyIn} days.`,'Generators may stop before resupply.','Reduce non-critical loads or request an earlier resupply.','Forecast: days left = stock ÷ burn rate (burn grows as heating demand grows).');
 const pd=daysOf(s,s.inv[3]);if(pd<s.resupplyIn)add('parts','warning','Spare parts running low','Logistics','fuel','/logistics',`${r1(pd)} days of spare parts at current usage.`,'Repairs (e.g. generator bearings) may be delayed.','Prioritise critical spares in the next resupply.','Forecast: stock ÷ average usage < days to resupply.');
 if(m.deficit>0)add('deficit','critical','Generation shortfall','Energy','bat','/energy',`Demand exceeds capacity by ${r1(m.deficit)} kW.`,'Battery discharging; critical loads at risk.','Shed non-critical loads and restore generation.','Rule: demand > available capacity.');
 if(s.env.temp<settings.tempWarn)add('cold','warning','Extreme cold','Environment',null,'/environment',`Temperature ${r1(s.env.temp)} °C.`,'Heating demand and fuel burn will rise.','Review energy forecast.',`Rule: temperature < ${settings.tempWarn} °C.`);
 if(s.env.wind>settings.windWarn)add('wind','warning','High winds','Environment','comms','/environment',`Wind ${r1(s.env.wind)} m/s.`,'Comms degradation and drifting snow.','Limit outdoor work.',`Rule: wind > ${settings.windWarn} m/s.`);
 const ids=new Set(out.map(a=>a.id));Object.keys(s.seen).forEach(k=>{if(!ids.has(k)){delete s.seen[k];delete s.acked[k]}});
 const rank={critical:0,warning:1,info:2};return out.sort((a,b)=>rank[a.severity]-rank[b.severity])}
const status=s=>{const a=alerts(s);return a.some(x=>x.severity==='critical')?'Critical':a.length?'Attention':'Operational'};
const envNow=s=>Object.fromEntries(Object.entries(s.env).map(([k,v])=>[k,r1(v)]));
const chain=s=>{const m=calc(s),f=s.inv[0];return[{k:'Temperature',v:`${r1(s.env.temp)} °C`},{k:'Heating demand',v:`${r1(m.heat)} kW`},{k:'Total demand',v:`${r1(m.demand)} kW`},{k:'Fuel burn',v:`${Math.round(rateOf(s,f))} L/day`},{k:'Fuel left',v:`${r1(daysOf(s,f))} days`}]};
const invOut=s=>s.inv.map(i=>{const d=daysOf(s,i),pct=i.stock/i.cap*100;return{k:i.k,name:i.name,unit:i.unit,stock:Math.round(i.stock),cap:i.cap,pct:r1(pct),rate:r1(rateOf(s,i)),daysLeft:r1(d),min:i.min,belowMin:pct<i.min,risk:risk(s,d)}});
const snap=s=>{const m=calc(s),d=daysOf(s,s.inv[0]);return{capacity:r1(m.cap),demand:r1(m.demand),deficit:r1(m.deficit),batteryHours:m.deficit>0?r1(s.battery.kwh*s.battery.pct/100/m.deficit):null,fuelDays:r1(d),fuelGap:r1(d-s.resupplyIn),resupplyIn:s.resupplyIn}};

const st=(q,r,n)=>{q.s=S[q.params.id];q.s?n():r.status(404).json({error:'Unknown station'})};
const who=q=>q.get('x-user');
app.get('/api/health',(q,r)=>r.json({ok:true,simulated:true}));
app.post('/api/login',(q,r)=>{const u=USERS.find(x=>x.email===q.body.email);if(!u||q.body.password!=='antarctic')return r.status(401).json({error:'Invalid credentials (demo password: antarctic)'});log(u.name,'Logged in');r.json({user:u})});
app.get('/api/stations',(q,r)=>r.json({ts:Date.now(),age:Date.now()-lastTick,simulated:true,stations:Object.values(S).map(s=>({id:s.id,name:s.name,status:status(s)}))}));
app.get('/api/stations/:id/overview',st,(q,r)=>{const s=q.s,m=calc(s),f=s.inv[0],al=alerts(s);
 r.json({id:s.id,name:s.name,status:status(s),kpis:{gen:r1(m.output),demand:r1(m.demand),cap:r1(m.cap),fuelPct:Math.round(f.stock/f.cap*100),fuelDays:r1(daysOf(s,f)),battery:r1(s.battery.pct),normal:s.assets.filter(a=>a.status==='normal').length,total:s.assets.length},
  env:envNow(s),alerts:al.filter(a=>!a.acked).slice(0,4),alertCount:{critical:al.filter(a=>a.severity==='critical'&&!a.acked).length,warning:al.filter(a=>a.severity==='warning'&&!a.acked).length},assets:s.assets,chain:chain(s)})});
app.get('/api/stations/:id/assets',st,(q,r)=>r.json({assets:q.s.assets,env:envNow(q.s)}));
app.get('/api/stations/:id/energy',st,(q,r)=>{const s=q.s,m=calc(s),b=s.baseLoad;
 r.json({history:s.hist,now:{gen:r1(m.output),demand:r1(m.demand),cap:r1(m.cap),deficit:r1(m.deficit),battery:r1(s.battery.pct),kwh:s.battery.kwh,fuel:invOut(s)[0]},
  breakdown:[{name:'Heating',value:r1(m.heat)},{name:'Living',value:r1(b*.3)},{name:'Laboratories',value:r1(b*.35)},{name:'Water',value:r1(b*.15)},{name:'Comms & other',value:r1(b*.2)}],chain:chain(s)})});
app.get('/api/stations/:id/logistics',st,(q,r)=>r.json({items:invOut(q.s),resupply:{inDays:q.s.resupplyIn,date:day(q.s.resupplyIn),schedule:[{date:day(q.s.resupplyIn),cargo:'Diesel, fresh food, spare parts',status:'Scheduled'},{date:day(q.s.resupplyIn+60),cargo:'Medical, general stores',status:'Planned'}]}}));
app.post('/api/stations/:id/inventory',st,(q,r)=>{const i=q.s.inv.find(x=>x.k===q.body.k),v=+q.body.stock;if(!i||!(v>=0))return r.status(400).json({error:'Bad input'});i.stock=Math.min(v,i.cap);log(who(q),`Updated ${i.name} stock at ${q.s.name} to ${i.stock}`);r.json({ok:true})});
app.get('/api/stations/:id/environment',st,(q,r)=>{const s=q.s,e=s.env,imp=[];
 if(e.temp<-25)imp.push(`Extreme cold (${r1(e.temp)} °C) → heating demand rises → energy consumption and fuel burn increase.`);else imp.push(`Temperature ${r1(e.temp)} °C → heating load is ${r1(calc(s).heat)} kW.`);
 if(e.wind>15)imp.push(`Strong wind (${r1(e.wind)} m/s) → comms link degrades and snow drifts around modules.`);
 if(e.vis<3)imp.push('Low visibility → restrict outdoor travel.');if(e.pressure<965)imp.push('Falling pressure → storm may be approaching.');
 r.json({now:envNow(s),history:s.hist,implications:imp})});
app.get('/api/stations/:id/alerts',st,(q,r)=>r.json({alerts:alerts(q.s)}));
app.post('/api/alerts/:id/acknowledge',(q,r)=>{const s=S[q.params.id.split(':')[0]];if(!s)return r.status(404).json({error:'Unknown alert'});s.acked[q.params.id]=who(q);log(who(q),`Acknowledged alert ${q.params.id}`);r.json({ok:true})});
app.get('/api/stations/:id/predictions',st,(q,r)=>{const s=q.s,e=s.env,m=calc(s);
 const forecast=[...Array(24)].map((_,h)=>{const temp=e.temp+2.5*Math.sin((h-4)/24*6.283)-(s.cold?6*Math.exp(-((h-14)**2)/30):0);return{h:`+${h}h`,temp:r1(temp),demand:r1(s.baseLoad+Math.max(0,-5-temp)*.9+10+(h>=6&&h<=20?4:0)),capacity:r1(m.cap)}});
 const anomalies=s.assets.filter(a=>a.status!=='normal'&&a.online).map(a=>{const r0=a.readings[0],h=a.hist.slice(-10),slope=h.length>1?(h[h.length-1]-h[0])/(h.length-1):0;
  const gen=a.type==='generator';const hrs=gen&&slope>.02?r1((settings.vibCrit-a.vib)/slope*10/60):null;
  return{assetId:a.id,name:a.name,severity:a.status,metric:r0.k,value:`${r0.v} ${r0.u}`,
   reason:gen?`Vibration is ${r0.v} mm/s, ${(r0.v/2.2).toFixed(1)}× the 2.2 mm/s baseline and rising ~${(slope*6).toFixed(2)} mm/s per simulated hour.`:`Rule-based: ${r0.k} ${r0.v} ${r0.u} is outside its normal range.`,
   urgency:hrs>0?`≈ ${hrs} simulated hours until critical threshold at current trend`:gen&&a.vib>settings.vibCrit?'Past critical threshold – inspect now':'Inspect at next maintenance window',trend:a.hist}});
 r.json({forecast,shortageHours:forecast.filter(x=>x.demand>x.capacity).length,peak:Math.max(...forecast.map(x=>x.demand)),anomalies,resources:invOut(s).map(i=>({name:i.name,daysLeft:i.daysLeft,resupplyIn:s.resupplyIn,risk:i.risk,pct:i.pct}))})});
app.post('/api/simulations',(q,r)=>{const{stationId,scenario,assetId,value}=q.body,s=S[stationId];if(!s)return r.status(404).json({error:'Unknown station'});
 const c=structuredClone(s),v=+value,notes=[];
 switch(scenario){
  case'generator_failure':{const a=c.assets.find(x=>x.id===(assetId||'gen2'));if(a)a.online=false;notes.push(`${a?.name} taken offline.`);break}
  case'temp_drop':c.env.temp-=v||15;notes.push(`Temperature falls by ${v||15} °C → heating demand rises.`);break;
  case'demand_increase':c.baseLoad*=1+(v||25)/100;notes.push(`Base load +${v||25}%.`);break;
  case'delayed_resupply':c.resupplyIn+=v||14;notes.push(`Resupply delayed by ${v||14} days.`);break;
  case'reduced_generation':c.capFactor=1-(v||30)/100;notes.push(`Generation capacity reduced by ${v||30}%.`);break;
  default:return r.status(400).json({error:'Unknown scenario'});}
 const before=snap(s),after=snap(c),recs=[];
 if(after.deficit>0){recs.push('Shed non-critical loads first (labs, lighting, workshops).');recs.push('Start standby generation or repair the faulty unit.')}
 if(after.fuelGap<0){recs.push('Fuel will run out before resupply: reduce heating setpoints and request an earlier resupply.')}
 if(!recs.length)recs.push('No immediate action required beyond monitoring.');
 log(who(q),`Ran simulation "${scenario}" for ${s.name}`);r.json({simulated:true,before,after,notes,recs})});
app.get('/api/stations/:id/maintenance',st,(q,r)=>r.json({tasks:q.s.tasks,assets:q.s.assets.map(a=>({id:a.id,name:a.name,type:a.type,status:a.status,hours:a.hours,last:a.last,next:a.next}))}));
app.post('/api/maintenance',(q,r)=>{const s=S[q.body.stationId];if(!s||!q.body.title)return r.status(400).json({error:'Bad input'});s.tasks.unshift({id:s.nextTask++,assetId:q.body.assetId,title:q.body.title,status:'Open',due:q.body.due||day(7),parts:q.body.parts||'-',by:who(q)});log(who(q),`Created maintenance task at ${s.name}: ${q.body.title}`);r.json({ok:true})});
app.post('/api/maintenance/:tid/complete',(q,r)=>{const s=S[q.body.stationId],t=s?.tasks.find(x=>x.id===+q.params.tid);if(!t)return r.status(404).json({error:'Not found'});t.status='Done';
 const a=s.assets.find(x=>x.id===t.assetId);if(a?.drift){a.drift=false;a.vib=2.2}log(who(q),`Completed task #${t.id} at ${s.name}`);r.json({ok:true})});
app.get('/api/settings',(q,r)=>r.json(settings));
app.post('/api/settings',(q,r)=>{if(q.get('x-role')!=='admin')return r.status(403).json({error:'Admins only'});Object.keys(settings).forEach(k=>{if(k in q.body&&!isNaN(+q.body[k]))settings[k]=+q.body[k]});log(who(q),'Updated alert thresholds');r.json(settings)});
app.get('/api/audit',(q,r)=>r.json({audit}));
app.listen(4000,()=>console.log('Simulated API on http://localhost:4000'));
