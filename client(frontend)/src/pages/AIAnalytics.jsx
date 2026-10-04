import {useState,useEffect} from 'react';import {LineChart,Line,BarChart,Bar as RBar,XAxis,YAxis,Tooltip,CartesianGrid,Legend,ResponsiveContainer,Cell} from 'recharts';
import {Brain,Activity,TrendingUp,Shield,Lightbulb} from 'lucide-react';
import {useApp} from '../context.jsx';import {useLive,api} from '../api.js';import {Card,Badge,Stat,Loading,Title,COL,tip} from '../components/ui.jsx';
export default function AIAnalytics(){const {station}=useApp();
  const [d]=useLive(`/api/stations/${station}/predictions`);
  const [mlForecast]=useLive(`/api/ml/stations/${station}/forecast`,10000);
  const [mlAnomalies]=useLive(`/api/ml/stations/${station}/anomalies`,10000);
  const [mlHealth]=useLive('/api/ml/health',15000);
  const [open,setOpen]=useState({});
  if(!d)return <Loading/>;
  const mlUp=mlHealth&&mlHealth.status!=='UNAVAILABLE';
  const method=d.method||'RULE_BASED';
  return <><Title sub={mlUp?'ML models active — hybrid predictions powered by trained models':'Rule-based detection (ML service offline — connect for enhanced predictions)'}>AI Analytics &amp; Predictive Maintenance</Title>

    {/* ML Service Status Banner */}
    <Card className={mlUp?'bannerok':'bannerbad'}>
      <div className="row" style={{justifyContent:'space-between',alignItems:'center'}}>
        <div className="row" style={{gap:12,alignItems:'center'}}>
          <Brain size={22}/>
          <div><h2 style={{margin:0}}>{mlUp?'🟢 AI/ML Engine Online':'🔴 AI/ML Engine Offline'}</h2>
            <small className="mu">{mlUp
              ?`Models: Anomaly ${mlHealth.models_loaded?.isolation_forest?'✅':'❌'} · Energy ${mlHealth.models_loaded?.energy_model?'✅':'❌'} · Fuel ${mlHealth.models_loaded?.fuel_model?'✅':'❌'}`
              :'Backend is using rule-based fallback logic. Start the AI/ML service on port 8001.'}</small>
          </div>
        </div>
        <Badge s={mlUp?'ok':'critical'}>{mlUp?'CONNECTED':'DISCONNECTED'}</Badge>
      </div>
    </Card>

    {/* ML KPIs */}
    {mlForecast&&<div className="g g4" style={{marginTop:16}}>
      <Stat icon={TrendingUp} tone="lav" label="ML Predicted Demand" value={mlForecast.energy?.predicted_demand!=null?`${mlForecast.energy.predicted_demand} kW`:'—'} sub="Next hour (GradientBoosting)"/>
      <Stat icon={Activity} tone="peach" label="Fuel Depletion" value={mlForecast.inventory?.days_to_depletion!=null?`${mlForecast.inventory.days_to_depletion} days`:'—'} sub="ML projected"/>
      <Stat icon={Shield} tone="mint" label="Station Health" value={mlForecast.health?.overall_health_index!=null?`${mlForecast.health.overall_health_index}/100`:'—'} sub="ML composite index"/>
      <Stat icon={Brain} tone="sky" label="Method" value={method} sub={d.sourceType||'PREDICTED'}/>
    </div>}

    {/* Anomaly Detection */}
    <Card title="A · Anomaly Detection (ML-powered)" className="mt">
      {mlAnomalies&&mlAnomalies.anomalies?.length>0
        ?mlAnomalies.anomalies.map(a=><div key={a.assetId} className={`alert ${a.ml?.severity==='Critical'?'critical':a.ml?.severity==='Warning'?'warning':'info'}`}>
          <div className="row" style={{justifyContent:'space-between'}}>
            <b>{a.name} ({a.type})</b>
            <div className="row" style={{gap:8}}>
              <Badge s={a.status}>{a.status}</Badge>
              {a.ml?.score!=null&&<Badge s={a.ml.severity==='Critical'?'critical':a.ml.severity==='Warning'?'warning':'ok'}>ML: {a.ml.severity} ({a.ml.score})</Badge>}
            </div>
          </div>
        </div>)
        :null}
      {d.anomalies.length===0&&(!mlAnomalies||!mlAnomalies.anomalies?.some(a=>a.ml?.severity!=='Normal'))&&<p className="mu">No anomalies detected ✨</p>}
      {d.anomalies.map(a=><div key={a.assetId} className={`alert ${a.severity}`}><div className="row" style={{justifyContent:'space-between'}}><b>{a.name} — {a.metric} {a.value}</b><Badge s={a.severity}/></div>
        <small>⏱ {a.urgency}</small><button className="chip" onClick={()=>setOpen({...open,[a.assetId]:!open[a.assetId]})}>{open[a.assetId]?'Hide':'Why this alert?'}</button>
        {open[a.assetId]&&<div><p style={{margin:'8px 0'}}>{a.reason}</p><ResponsiveContainer width="100%" height={90}><LineChart data={a.trend.map((v,i)=>({i,v}))}><YAxis hide domain={['auto','auto']}/><Line dataKey="v" stroke={COL.rose} strokeWidth={2.5} dot={false} isAnimationActive={false}/></LineChart></ResponsiveContainer></div>}</div>)}
    </Card>

    {/* Energy Forecast */}
    <Card title="B · Energy forecast (next 24 h)" className="mt" right={<Badge s={d.shortageHours?'critical':'ok'}>{d.shortageHours?`${d.shortageHours} h of shortage`:`peak ${d.peak} kW — within capacity`}</Badge>}>
      <ResponsiveContainer width="100%" height={220}><LineChart data={d.forecast}><CartesianGrid strokeDasharray="3 3" stroke="#e7e1f6"/><XAxis dataKey="h" fontSize={10} interval={2}/><YAxis fontSize={11}/><Tooltip {...tip}/><Legend/>
        <Line dataKey="demand" name="Predicted demand" stroke={COL.peach} strokeWidth={3} dot={false}/><Line dataKey="capacity" name="Available capacity" stroke={COL.sky} strokeDasharray="5 4" dot={false}/><Line dataKey="temp" name="Forecast temp °C" stroke={COL.lav} dot={false}/></LineChart></ResponsiveContainer>
      <p className="mu" style={{fontSize:13}}>{d.forecast[0]?.sourceType==='PREDICTED_ML'?'🤖 Demand powered by trained GradientBoosting ML model, blended with rule-based capacity.':'📐 Rule-based: colder temperature → higher heating demand → higher total demand.'}</p>
    </Card>

    {/* Resource Forecast */}
    <Card title="C · Resource forecast (days left vs days to resupply)" className="mt"><ResponsiveContainer width="100%" height={240}><BarChart data={d.resources.map(r=>({...r,daysLeft:Math.min(r.daysLeft,120)}))}><CartesianGrid strokeDasharray="3 3" stroke="#e7e1f6"/><XAxis dataKey="name" fontSize={11}/><YAxis fontSize={11}/><Tooltip {...tip}/><Legend/>
      <RBar dataKey="daysLeft" name="Days left (capped 120)">{d.resources.map((r,i)=><Cell key={i} fill={r.risk==='critical'?COL.rose:r.risk==='warning'?COL.butter:COL.mint}/>)}</RBar><RBar dataKey="resupplyIn" name="Days to resupply" fill={COL.sky}/></BarChart></ResponsiveContainer>
      {d.resources[0]?.method==='ML_MODEL'&&<p className="mu" style={{fontSize:13}}>🤖 Resource depletion estimated by trained fuel consumption model.</p>}
    </Card>

    {/* Recommendations */}
    {mlForecast&&mlForecast.recommendations?.length>0&&<Card title="D · AI Recommendations" className="mt">
      {mlForecast.recommendations.map((r,i)=><div key={i} className="alert info"><Lightbulb size={16} style={{marginRight:8}}/><b>{r}</b></div>)}
    </Card>}
  </>}
