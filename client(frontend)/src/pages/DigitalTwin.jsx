import {useSearchParams,useNavigate} from 'react-router-dom';import {LineChart,Line,YAxis,ResponsiveContainer,Tooltip} from 'recharts';
import {useApp} from '../context.jsx';import {useLive} from '../api.js';import {Card,Badge,Loading,Title,COL,tip} from '../components/ui.jsx';import TwinMap from '../components/TwinMap.jsx';
export default function DigitalTwin(){const {station}=useApp();const [sp,setSp]=useSearchParams();const nav=useNavigate();
  const [d]=useLive(`/api/stations/${station}/assets`,3000);if(!d)return <Loading/>;
  const sel=d.assets.find(a=>a.id===sp.get('asset'));
  return <><Title sub="Click any module to inspect live (simulated) readings">Digital Twin · {station==='maitri'?'Maitri':'Bharati'}</Title>
    <div className="g g21"><Card title="Station layout" right={<div className="row"><Badge s="normal">Normal</Badge><Badge s="warning">Warning</Badge><Badge s="critical">Critical</Badge><Badge s="offline">Offline</Badge></div>}>
      <TwinMap assets={d.assets} selected={sel?.id} onSelect={id=>setSp({asset:id})} dir={d.env.dir}/><p className="mu" style={{fontSize:12}}>Dashed lines show power / fuel connections. Lines turn red when a linked asset has a problem.</p></Card>
      <Card title={sel?sel.name:'Select an asset'} right={sel&&<Badge s={sel.status}/>}>
        {!sel&&<p className="mu">👈 Click a generator, battery bank, lab… to see readings, trend and maintenance info.</p>}
        {sel&&<><div className="g g2">{sel.readings.map(r=><div key={r.k} className="mini"><small>{r.k}</small><b>{r.v} {r.u}</b></div>)}</div>
          <h4>Trend · {sel.readings[0].k}</h4><ResponsiveContainer width="100%" height={110}><LineChart data={sel.hist.map((v,i)=>({i,v}))}><YAxis hide domain={['auto','auto']}/><Tooltip {...tip}/><Line dataKey="v" stroke={COL.lav} strokeWidth={2.5} dot={false} isAnimationActive={false}/></LineChart></ResponsiveContainer>
          <p className="mu" style={{fontSize:13}}>Operating hours: {sel.hours.toLocaleString()} · Last service: {sel.last} · Next: {sel.next}</p>
          <div className="row"><button className="btn ghost" onClick={()=>nav(`/maintenance?asset=${sel.id}`)}>🔧 Maintenance</button>
            {sel.type==='generator'&&<button className="btn" onClick={()=>nav(`/simulation?scenario=generator_failure&asset=${sel.id}`)}>⚡ Simulate failure</button>}</div></>}
      </Card></div></>}
