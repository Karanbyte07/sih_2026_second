import {Link} from 'react-router-dom';import {Zap,Fuel,BatteryCharging,Cpu,Thermometer,Wind,Gauge,Eye,Brain} from 'lucide-react';
import {AreaChart,Area,XAxis,YAxis,Tooltip,CartesianGrid,ResponsiveContainer} from 'recharts';
import {useApp} from '../context.jsx';import {useLive} from '../api.js';import {Card,Stat,Badge,Loading,Title,Chain,COL,tip} from '../components/ui.jsx';import TwinMap from '../components/TwinMap.jsx';
export default function Overview(){const {station,setStation}=useApp();
  const [sts]=useLive('/api/stations');const [o]=useLive(`/api/stations/${station}/overview`);const [en]=useLive(`/api/stations/${station}/energy`);
  const [mlForecast]=useLive(`/api/ml/stations/${station}/forecast`,10000);
  const [mlHealth]=useLive('/api/ml/health',15000);
  if(!o||!sts||!en)return <Loading/>;const k=o.kpis,e=o.env;
  const mlUp=mlHealth&&mlHealth.status!=='UNAVAILABLE';
  return <><Title sub="Live (simulated) status across both stations">Command Centre · {o.name}</Title>
    <div className="g g2">{sts.stations.map(s=><div key={s.id} onClick={()=>setStation(s.id)} className={`card hov station ${s.id===station?'sel':''}`}><div><h2>{s.id==='maitri'?'🏔️ Maitri':'🧊 Bharati'}</h2><small className="mu">{s.id===station?'Currently viewing':'Click to switch'}</small></div><Badge s={s.status}/></div>)}</div>
    <div className="g g4" style={{marginTop:16}}>
      <Stat icon={Zap} tone="lav" label="Power" value={`${k.gen} kW`} sub={`demand ${k.demand} · capacity ${k.cap} kW`}/>
      <Stat icon={Fuel} tone="peach" label="Fuel reserve" value={`${k.fuelPct}%`} sub={`${k.fuelDays} days at current burn`}/>
      <Stat icon={BatteryCharging} tone="mint" label="Battery" value={`${k.battery}%`} sub="Battery bank 400 kWh"/>
      <Stat icon={Brain} tone="sky" label="AI/ML Status" value={mlUp?'Online':'Offline'} sub={mlForecast?.health?.overall_health_index!=null?`Health index: ${mlForecast.health.overall_health_index}/100`:'Connect ML service on :8001'}/></div>
    <div className="g g21" style={{marginTop:16}}>
      <Card title="Station digital twin" right={<Link className="link-a" to="/twin">Open full twin →</Link>}><TwinMap assets={o.assets} dir={e.dir} compact/></Card>
      <Card title="Active alerts" right={<Link className="link-a" to="/alerts">All →</Link>}>
        {o.alerts.length===0&&<p className="mu">All clear ✨</p>}
        {o.alerts.map(a=><Link key={a.id} to={a.link} className={`alert ${a.severity}`}><b>{a.title}</b><small>{a.source} — {a.desc}</small></Link>)}</Card></div>
    <Card title="How it's all connected" className="mt"><Chain items={o.chain}/></Card>
    <div className="g g21" style={{marginTop:16}}>
      <Card title="Generation vs demand (kW)"><ResponsiveContainer width="100%" height={230}><AreaChart data={en.history}><CartesianGrid strokeDasharray="3 3" stroke="#e7e1f6"/><XAxis dataKey="t" hide/><YAxis fontSize={11}/><Tooltip {...tip}/>
        <Area dataKey="gen" name="Generation" stroke={COL.lav} fill={COL.lav} fillOpacity={.35} isAnimationActive={false}/><Area dataKey="demand" name="Demand" stroke={COL.peach} fill={COL.peach} fillOpacity={.3} isAnimationActive={false}/></AreaChart></ResponsiveContainer></Card>
      <Card title="Environment"><div className="g g2"><Stat icon={Thermometer} tone="sky" label="Temp" value={`${e.temp}°C`}/><Stat icon={Wind} tone="mint" label="Wind" value={`${e.wind} m/s`}/><Stat icon={Gauge} tone="lav" label="Pressure" value={`${e.pressure} hPa`}/><Stat icon={Eye} tone="butter" label="Visibility" value={`${e.vis} km`}/></div></Card></div></>}

