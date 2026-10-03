import {useState} from 'react';import {useSearchParams} from 'react-router-dom';import {BarChart,Bar as RBar,XAxis,YAxis,Tooltip,CartesianGrid,Legend,ResponsiveContainer} from 'recharts';
import {useApp} from '../context.jsx';import {useLive,api} from '../api.js';import {Card,Loading,Title,COL,tip} from '../components/ui.jsx';
const SC=[['generator_failure','Generator failure','⚡',null],['temp_drop','Extreme temperature drop','🥶',{label:'Drop (°C)',min:5,max:30,def:15}],['demand_increase','Increased energy demand','📈',{label:'Increase (%)',min:5,max:60,def:25}],['delayed_resupply','Delayed resupply','🚢',{label:'Delay (days)',min:3,max:30,def:14}],['reduced_generation','Reduced generation','🔻',{label:'Reduction (%)',min:10,max:60,def:30}]];
const ROWS=[['Capacity (kW)','capacity'],['Demand (kW)','demand'],['Energy deficit (kW)','deficit'],['Battery lasts (h)','batteryHours'],['Fuel days left','fuelDays'],['Fuel margin vs resupply (d)','fuelGap']];
export default function Simulation(){const {station,can}=useApp();const [sp]=useSearchParams();const [as]=useLive(`/api/stations/${station}/assets`,60000);
  const [sc,setSc]=useState(sp.get('scenario')||'generator_failure');const [gen,setGen]=useState(sp.get('asset')||'gen2');const [val,setVal]=useState({});const [res,setRes]=useState(null);const [busy,setBusy]=useState(false);
  if(!as)return <Loading/>;const cur=SC.find(s=>s[0]===sc),p=cur[3];const v=p?(val[sc]??p.def):null;
  const run=async()=>{setBusy(true);setRes(await api('/api/simulations',{method:'POST',body:{stationId:station,scenario:sc,assetId:gen,value:v}}));setBusy(false)};
  const f=x=>x===null||x===undefined?'—':x;
  return <><Title sub="Test an operational scenario and compare before vs after">What-If Simulation</Title>
    <div className="banner">🧪 SIMULATION — results are predictions only. Nothing changes in station operations.</div>
    <div className="g g3 mt">{SC.map(([id,l,ic])=><div key={id} className={`card hov pick ${sc===id?'sel':''}`} onClick={()=>{setSc(id);setRes(null)}}><span style={{fontSize:28}}>{ic}</span><b>{l}</b></div>)}</div>
    <Card title="Parameters" className="mt"><div className="row">
      {sc==='generator_failure'&&<select value={gen} onChange={e=>setGen(e.target.value)}>{as.assets.filter(a=>a.type==='generator').map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select>}
      {p&&<><span>{p.label}</span><input type="range" min={p.min} max={p.max} value={v} onChange={e=>setVal({...val,[sc]:+e.target.value})}/><b>{v}</b></>}
      <button className="btn" disabled={busy||!can('simulate')} onClick={run}>{busy?'Running…':'▶ Run simulation'}</button>{!can('simulate')&&<small className="mu">Your role can't run simulations</small>}</div></Card>
    {res&&<><Card title="Before vs after (SIMULATED)" className="mt"><div className="g g21"><table><thead><tr><th>Metric</th><th>Now</th><th>Simulated</th></tr></thead><tbody>{ROWS.map(([l,k])=>{const worse=res.after[k]!==res.before[k]&&(k==='deficit'?res.after[k]>res.before[k]:k==='demand'?res.after[k]>res.before[k]:res.after[k]<res.before[k]);
        return <tr key={k}><td>{l}</td><td>{f(res.before[k])}</td><td style={{fontWeight:700,color:worse?'#e8607f':'inherit'}}>{f(res.after[k])}</td></tr>})}</tbody></table>
      <ResponsiveContainer width="100%" height={220}><BarChart data={[{n:'Now',cap:res.before.capacity,dem:res.before.demand},{n:'Simulated',cap:res.after.capacity,dem:res.after.demand}]}><CartesianGrid strokeDasharray="3 3" stroke="#e7e1f6"/><XAxis dataKey="n"/><YAxis fontSize={11}/><Tooltip {...tip}/><Legend/><RBar dataKey="cap" name="Capacity kW" fill={COL.sky} radius={6}/><RBar dataKey="dem" name="Demand kW" fill={COL.peach} radius={6}/></BarChart></ResponsiveContainer></div></Card>
      <Card title="Suggested response" className="mt">{res.notes.map(n=><p key={n} className="mu">• {n}</p>)}{res.recs.map(r=><div key={r} className="alert info"><b>{r}</b></div>)}</Card></>}</>}
