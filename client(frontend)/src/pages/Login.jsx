import {useState} from 'react';import {Snowflake} from 'lucide-react';import {api} from '../api.js';import {useApp} from '../context.jsx';
const DEMO=[['admin@ncpor.in','Administrator'],['ops@ncpor.in','Operations manager'],['maint@ncpor.in','Maintenance (Bharati)'],['logistics@ncpor.in','Logistics (Maitri)']];
export default function Login(){const {login}=useApp();const [email,setE]=useState('admin@ncpor.in'),[password,setP]=useState('antarctic'),[err,setErr]=useState('');
  const go=async()=>{try{const r=await api('/api/login',{method:'POST',body:{email,password}});login({...r.user,token:r.token})}catch(e){setErr(e.message)}};
  return <div className="login"><div className="card"><div style={{textAlign:'center'}}><Snowflake size={42} color="#8b6fe0"/><h1 style={{margin:'6px 0'}}>Antarctic Twin</h1><p className="mu">Remote management of Maitri &amp; Bharati stations</p></div>
    <label>Email<input value={email} onChange={e=>setE(e.target.value)}/></label><label>Password<input type="password" value={password} onChange={e=>setP(e.target.value)} onKeyDown={e=>e.key==='Enter'&&go()}/></label>
    {err&&<p style={{color:'#e8607f'}}>{err}</p>}<button className="btn" style={{width:'100%'}} onClick={go}>Sign in</button>
    <p className="mu" style={{fontSize:12,marginTop:16}}>Demo accounts (password <b>antarctic</b>):</p>
    <div className="row">{DEMO.map(([e,l])=><button key={e} className="chip" onClick={()=>setE(e)}>{l}</button>)}</div></div></div>}
