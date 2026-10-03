import {useEffect,useState} from 'react';
let sess=null;export const setSess=u=>{sess=u};
export async function api(path,opt={}){
  const r=await fetch(path,{...opt,headers:{'Content-Type':'application/json','x-user':sess?.name||'guest','x-role':sess?.role||''},body:opt.body?JSON.stringify(opt.body):undefined});
  const j=await r.json().catch(()=>({}));if(!r.ok)throw new Error(j.error||r.statusText);return j}
// Polls an endpoint. Returns [data, reload, hadError]
export function useLive(path,ms=4000){
  const [st,setSt]=useState({path:null,data:null,err:false});const [n,setN]=useState(0);
  useEffect(()=>{let on=true;const go=()=>api(path).then(d=>on&&setSt({path,data:d,err:false})).catch(()=>on&&setSt(s=>({...s,err:true})));
    go();const i=setInterval(go,ms);return()=>{on=false;clearInterval(i)}},[path,ms,n]);
  return [st.path===path?st.data:null,()=>setN(x=>x+1),st.err]}
