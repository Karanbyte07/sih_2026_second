import {NavLink,Outlet,Link} from 'react-router-dom';
import {LayoutDashboard,Box,Building2,Zap,Package,CloudSnow,Brain,FlaskConical,Bell,Wrench,Settings,Sun,Moon,LogOut,Wifi,WifiOff,Snowflake} from 'lucide-react';
import {useApp} from '../context.jsx';import {useLive} from '../api.js';
const NAV=[['/','Overview',LayoutDashboard],['/twin','Digital Twin',Box],['/infrastructure','Infrastructure',Building2],['/energy','Energy',Zap],['/logistics','Logistics',Package],['/environment','Environment',CloudSnow],['/ai','AI & Predictions',Brain],['/simulation','Simulations',FlaskConical],['/alerts','Alerts',Bell],['/maintenance','Maintenance',Wrench],['/settings','Settings',Settings]];
export default function Layout(){
  const {user,station,setStation,theme,setTheme,logout}=useApp();
  const [sts,,err]=useLive('/api/stations',5000);const [ov]=useLive(`/api/stations/${station}/overview`,5000);
  const link=err?'offline':sts&&sts.age>20000?'stale':'online';const n=ov?ov.alertCount.critical+ov.alertCount.warning:0;
  return <div className="app"><aside className="side"><div className="brand"><Snowflake size={24}/> <div><b>ANTARCTIC TWIN</b><small>Maitri · Bharati</small></div></div>
    <nav className="nav">{NAV.map(([to,l,I])=><NavLink key={to} to={to} end={to==='/'}><I size={18}/>{l}{l==='Alerts'&&n>0&&<em>{n}</em>}</NavLink>)}</nav>
    <div className="sidefoot">NCPOR · MoES<br/>SIH 2026 · PS 26060<br/>All values simulated</div></aside>
    <div><header className="top"><div className="tabs">{user.stations.map(id=><button key={id} className={`chip ${station===id?'on':''}`} onClick={()=>setStation(id)}>{id==='maitri'?'🏔️ Maitri':'🧊 Bharati'}</button>)}</div>
      <span className="badge info">SIMULATED DATA</span>
      <span className={`badge ${link==='online'?'ok':link==='stale'?'warn':'crit'}`}>{link==='offline'?<WifiOff size={12}/>:<Wifi size={12}/>} {link}</span>
      <div style={{flex:1}}/><Link to="/alerts" className="iconbtn" title="Alerts"><Bell size={18}/>{n>0&&<em>{n}</em>}</Link>
      <button className="iconbtn" onClick={()=>setTheme(theme==='light'?'dark':'light')}>{theme==='light'?<Moon size={18}/>:<Sun size={18}/>}</button>
      <div className="me"><b>{user.name}</b><small>{user.role}</small></div><button className="iconbtn" onClick={logout} title="Log out"><LogOut size={18}/></button></header>
      <main className="main page" key={station}><Outlet/></main></div></div>}
