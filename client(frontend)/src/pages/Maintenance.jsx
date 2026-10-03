import {useState} from 'react';import {useSearchParams} from 'react-router-dom';import {useApp} from '../context.jsx';import {useLive,api} from '../api.js';import {Card,Badge,Loading,Title} from '../components/ui.jsx';
export default function Maintenance(){const {station,can}=useApp();const [sp]=useSearchParams();const [d,reload]=useLive(`/api/stations/${station}/maintenance`,6000);
  const [f,setF]=useState({assetId:sp.get('asset')||'gen2',title:'',due:'',parts:''});if(!d)return <Loading/>;
  const add=async()=>{if(!f.title)return;await api('/api/maintenance',{method:'POST',body:{...f,stationId:station}});setF({...f,title:'',parts:''});reload()};
  const done=async t=>{await api(`/api/maintenance/${t.id}/complete`,{method:'POST',body:{stationId:station}});reload()};
  return <><Title sub="Service schedules, open tasks and spare parts">Asset &amp; Maintenance Management</Title>
    <Card title="New maintenance task"><div className="row"><select value={f.assetId} onChange={e=>setF({...f,assetId:e.target.value})}>{d.assets.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select>
      <input placeholder="Task description" value={f.title} onChange={e=>setF({...f,title:e.target.value})} style={{flex:1,minWidth:200}}/><input type="date" value={f.due} onChange={e=>setF({...f,due:e.target.value})}/><input placeholder="Parts needed" value={f.parts} onChange={e=>setF({...f,parts:e.target.value})}/>
      <button className="btn" disabled={!can('maintenance')} onClick={add}>Add task</button></div>{!can('maintenance')&&<small className="mu">Only maintenance staff and admins can add or complete tasks.</small>}</Card>
    <Card title="Tasks" className="mt"><table><thead><tr><th>#</th><th>Asset</th><th>Task</th><th>Due</th><th>Parts</th><th>Status</th><th/></tr></thead><tbody>
      {d.tasks.map(t=><tr key={t.id}><td>{t.id}</td><td>{d.assets.find(a=>a.id===t.assetId)?.name}</td><td>{t.title}</td><td>{t.due}</td><td>{t.parts}</td><td><Badge s={t.status==='Done'?'ok':'warn'}>{t.status}</Badge></td>
        <td>{t.status!=='Done'&&<button className="btn ghost" disabled={!can('maintenance')} onClick={()=>done(t)}>Mark done</button>}</td></tr>)}</tbody></table>
      <small className="mu">Tip: completing the Generator 02 inspection at Bharati clears its simulated vibration fault.</small></Card>
    <Card title="Inspection schedule" className="mt"><table><thead><tr><th>Asset</th><th>Status</th><th>Hours</th><th>Last service</th><th>Next inspection</th></tr></thead><tbody>
      {d.assets.map(a=><tr key={a.id}><td><b>{a.name}</b></td><td><Badge s={a.status}/></td><td>{a.hours.toLocaleString()}</td><td>{a.last}</td><td>{a.next}</td></tr>)}</tbody></table></Card></>}
