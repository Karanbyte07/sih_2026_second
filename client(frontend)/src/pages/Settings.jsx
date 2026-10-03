import {useEffect,useState} from 'react';import {useApp} from '../context.jsx';import {useLive,api} from '../api.js';import {Card,Badge,Title} from '../components/ui.jsx';
const LBL={vibWarn:'Vibration warning (mm/s)',vibCrit:'Vibration critical (mm/s)',batteryWarn:'Battery warning (%)',tempWarn:'Extreme cold (°C)',windWarn:'High wind (m/s)'};
export default function SettingsPage(){const {user,can}=useApp();const [s,setS]=useState(null);const [au]=useLive('/api/audit',5000);const [msg,setMsg]=useState('');
  useEffect(()=>{api('/api/settings').then(setS)},[]);
  const save=async()=>{try{setS(await api('/api/settings',{method:'POST',body:s}));setMsg('Saved ✔')}catch(e){setMsg(e.message)}};
  return <><Title sub="Profile, access, alert thresholds and audit log">Settings &amp; User Management</Title>
    <div className="g g2"><Card title="Profile"><p><b>{user.name}</b><br/>{user.email}</p><p>Role: <Badge s="info">{user.role}</Badge></p><p>Station access: {user.stations.map(x=><Badge key={x} s="ok">{x}</Badge>)}</p>
      <p className="mu" style={{fontSize:13}}>Roles: admin (everything) · ops (acknowledge alerts, run simulations) · maintenance (tasks) · logistics (inventory).</p></Card>
      <Card title="Alert thresholds">{s&&Object.keys(LBL).map(k=><label key={k} className="row" style={{justifyContent:'space-between'}}>{LBL[k]}<input type="number" style={{width:90}} disabled={!can('*')} value={s[k]} onChange={e=>setS({...s,[k]:e.target.value})}/></label>)}
        <div className="row"><button className="btn" disabled={!can('*')} onClick={save}>Save</button><small className="mu">{can('*')?msg:'Admins only'}</small></div></Card></div>
    <Card title="Audit log" className="mt"><table><thead><tr><th>Time</th><th>User</th><th>Action</th></tr></thead><tbody>{au?.audit.slice(0,15).map((a,i)=><tr key={i}><td>{new Date(a.t).toLocaleTimeString()}</td><td>{a.user}</td><td>{a.action}</td></tr>)}</tbody></table></Card></>}
