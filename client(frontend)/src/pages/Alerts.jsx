import {useState} from 'react';import {Link} from 'react-router-dom';import {useApp} from '../context.jsx';import {useLive,api} from '../api.js';import {Card,Badge,Loading,Title} from '../components/ui.jsx';
export default function Alerts(){const {station,can}=useApp();const [d,reload]=useLive(`/api/stations/${station}/alerts`,3000);const [f,setF]=useState('active');const [open,setOpen]=useState({});
  if(!d)return <Loading/>;const list=d.alerts.filter(a=>f==='all'||(f==='active'?!a.acked:f==='acknowledged'?a.acked:a.severity===f));
  const ack=async a=>{await api(`/api/alerts/${encodeURIComponent(a.id)}/acknowledge`,{method:'POST'});reload()};
  return <><Title sub="Critical alerts, warnings and recommended next steps">Alerts &amp; Notifications</Title>
    <div className="row" style={{marginBottom:12}}>{['active','critical','warning','acknowledged','all'].map(x=><button key={x} className={`chip ${f===x?'on':''}`} onClick={()=>setF(x)}>{x}</button>)}</div>
    {list.length===0&&<Card><p className="mu">Nothing here ✨</p></Card>}
    {list.map(a=><div key={a.id} className={`alert big ${a.severity} ${a.acked?'acked':''}`}><div className="row" style={{justifyContent:'space-between'}}><b style={{fontSize:16}}>{a.title} — {a.source}</b><div className="row"><Badge s={a.severity}/>{a.acked&&<Badge s="ok">acknowledged</Badge>}</div></div>
      <p style={{margin:'6px 0'}}>{a.desc}</p><small><b>Impact:</b> {a.impact}</small><small><b>Suggested action:</b> {a.action}</small><small>First seen {new Date(a.time).toLocaleString()}</small>
      {open[a.id]&&<small className="why">🧠 Why: {a.why}</small>}
      <div className="row" style={{marginTop:8}}><Link className="btn" to={a.link}>Open in {a.link.startsWith('/twin')?'Digital Twin':'related page'} →</Link><button className="chip" onClick={()=>setOpen({...open,[a.id]:!open[a.id]})}>Why?</button>
        {!a.acked&&<button className="btn ghost" disabled={!can('ack')} title={can('ack')?'':'Your role cannot acknowledge'} onClick={()=>ack(a)}>Acknowledge</button>}</div></div>)}</>}
